"""Intégration finale S9 — câblage des 8 pôles + cycle script→mémoire→agent→action.

Trois familles de tests :

1. **Câblage** : le registre Python (:mod:`argos_ops.poles.registry`) et les
   ``pole.yaml`` réels déclarent exactement les mêmes scripts ; les lectures
   cross-pôle (``reads_cross_pole``) pointent toutes vers des pôles réels ; chaque
   agent charge son contexte sans erreur.
2. **Orchestrateur de flotte** (:mod:`argos_ops.poles.fleet`) : le plan couvre les
   8 pôles ; kill-switch / breakers / daily_limit / cadence sont respectés ; le
   cycle live lance les scripts dûs puis réveille les bons agents.
3. **Cycle complet par pôle** : pour chacun des 8 pôles, un script déterministe
   réel écrit sa mémoire, puis (pôles 1-6 + Mémoire) l'agent la relit et agit —
   le tout hermétique sous un ``poles_root`` temporaire (``pole.yaml`` réels copiés).

asyncio_mode = "auto" (pyproject) → pas de décorateur sur les tests async.
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

from argos_ops.poles import fleet_runlog, memory, registry
from argos_ops.poles.agent import AgentResult, BaseAgent
from argos_ops.poles.base import BaseScript, ScriptResult, run_script
from argos_ops.poles.config import (
    CROSS_POLE_WILDCARD,
    POLES_DIR,
    list_poles,
    load_all_poles,
)

# Agents
from argos_ops.poles.direction.agent import DirectionAgent
from argos_ops.poles.direction.scripts.strategy_bot import StrategyBotScript
from argos_ops.poles.finance.agent import FinanceAgent
from argos_ops.poles.finance.scripts.rgpd_auditor import RGPDAuditorScript
from argos_ops.poles.fleet import FleetDecision, FleetPlan, plan_fleet, run_fleet_cycle
from argos_ops.poles.marketing.agent import MarketingAgent
from argos_ops.poles.marketing.scripts.media_list_builder import MediaListBuilderScript
from argos_ops.poles.memoire.agent import MemoireAgent
from argos_ops.poles.memoire.policy import MemoryPolicy
from argos_ops.poles.memoire.scripts.capability_router import CapabilityRouterScript
from argos_ops.poles.pub.agent import PubAgent
from argos_ops.poles.pub.scripts.ads_optimizer import AdsOptimizerScript
from argos_ops.poles.sre import breakers, killswitch
from argos_ops.poles.sre.scripts.bot_config_manager import BotConfigManagerScript
from argos_ops.poles.veille.agent import VeilleAgent
from argos_ops.poles.veille.scripts.trend_spotter import TrendSpotterScript
from argos_ops.poles.vente.agent import VenteAgent
from argos_ops.poles.vente.scripts.bloctel_guard import BloctelGuardScript

REAL_POLES = ("veille", "marketing", "pub", "vente", "finance", "direction", "memoire", "sre")
NOW = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)
OLD = NOW - timedelta(days=400)


def _copy_real_configs(tmp_path: Path) -> Path:
    """Copie tous les ``pole.yaml`` réels sous ``tmp_path/poles`` (byte-exact, accents préservés).

    Donne un ``poles_root`` hermétique mais fidèle : agents (dont les transversaux
    en ``reads_cross_pole: ["*"]``) et orchestrateur voient la vraie topologie.
    """
    root = tmp_path / "poles"
    for pole in REAL_POLES:
        dst = root / pole
        dst.mkdir(parents=True, exist_ok=True)
        shutil.copy(POLES_DIR / pole / "pole.yaml", dst / "pole.yaml")
    return root


def _launch(pole: str, script: str) -> FleetDecision:
    """Décision « launch » minimale pour cibler un cycle live sur un seul script."""
    return FleetDecision(
        pole=pole,
        script=script,
        verdict="launch",
        reason="test",
        schedule="0 0 * * *",
        last_run_at=None,
        next_run_at=None,
        runs_today=0,
        daily_limit=None,
        runnable=True,
    )


# =============================================================================
# 1. Câblage : registre ⇄ pole.yaml, lectures cross-pôle, chargement de contexte
# =============================================================================
def test_registry_matches_pole_yaml_real() -> None:
    """Le registre Python et les ``pole.yaml`` réels sont parfaitement cohérents."""
    assert registry.validate_registry() == []
    assert set(registry.POLE_SCRIPTS) == set(REAL_POLES)
    # Autant de couples (pôle, script) que de scripts déclarés dans les pole.yaml.
    declared = sum(len(cfg.scripts) for cfg in load_all_poles())
    assert len(registry.all_script_ids()) == declared
    # SRE = aucun agent ; les 7 autres pôles ont bien un agent câblé.
    assert registry.POLE_AGENTS["sre"] is None
    for pole in REAL_POLES:
        if pole != "sre":
            assert registry.agent_class(pole) is not None


def test_every_script_class_matches_its_pole() -> None:
    """Chaque classe enregistrée déclare le bon ``pole`` et un ``name`` non vide."""
    for pole, classes in registry.POLE_SCRIPTS.items():
        for cls in classes:
            assert cls.pole == pole
            assert cls.name


def test_cross_pole_reads_resolve_to_real_poles() -> None:
    """Toutes les lectures cross-pôle pointent vers ``"*"`` ou un pôle réel existant."""
    poles = set(list_poles())
    assert poles == set(REAL_POLES)
    for cfg in load_all_poles():
        for target in cfg.reads_cross_pole:
            assert target == CROSS_POLE_WILDCARD or target in poles, (
                f"{cfg.id} lit un pôle inconnu : {target!r}"
            )


async def test_every_agent_loads_context_hermetic(tmp_path: Path) -> None:
    """Chaque agent (y compris transversaux) charge son contexte sans lever."""
    root = _copy_real_configs(tmp_path)
    for pole, agent_cls in registry.POLE_AGENTS.items():
        if agent_cls is None:  # SRE — pas d'agent.
            continue
        agent: BaseAgent
        if pole == "memoire":  # constructeur particulier : target_pole positionnel.
            agent = agent_cls("veille", poles_root=root)
        else:
            agent = agent_cls(poles_root=root)
        ctx = await agent.load_context()
        assert ctx.pole == pole
        # Les pôles transversaux voient bien les autres pôles déclarés lisibles.
        cfg = next(c for c in load_all_poles(poles_root=root) if c.id == pole)
        if CROSS_POLE_WILDCARD in cfg.reads_cross_pole:
            # mémoire vide partout ⇒ cross_pole vide, mais aucune exception levée
            assert isinstance(ctx.cross_pole, dict)


# =============================================================================
# 2. Orchestrateur de flotte : plan + garde-fous + cycle live
# =============================================================================
async def test_plan_fleet_covers_all_eight_poles(tmp_path: Path) -> None:
    root = _copy_real_configs(tmp_path)
    plan = await plan_fleet(poles_root=root, now=NOW, dry_run=True)
    assert {d.pole for d in plan.decisions} == set(REAL_POLES)
    # Jamais journalisés ⇒ tous les scripts cadencés sont « dûs ».
    scheduled = sum(1 for cfg in load_all_poles(poles_root=root) for s in cfg.scripts if s.schedule)
    assert len(plan.to_launch) == scheduled
    # Les 2 scripts réactifs (schedule null) → skipped_no_schedule.
    no_sched = {(d.pole, d.script) for d in plan.decisions if d.verdict == "skipped_no_schedule"}
    assert no_sched == {("finance", "incident_logger"), ("direction", "decision_logger")}


async def test_plan_respects_killswitch_and_breaker(tmp_path: Path) -> None:
    root = _copy_real_configs(tmp_path)
    killswitch.set_script("trend_spotter", True, poles_root=root)
    breakers.trip("content_bot", "test S9", poles_root=root)
    plan = await plan_fleet(poles_root=root, now=NOW, dry_run=True)
    verdicts = {(d.pole, d.script): d.verdict for d in plan.decisions}
    assert verdicts[("veille", "trend_spotter")] == "skipped_frozen"
    assert verdicts[("marketing", "content_bot")] == "skipped_breaker"


async def test_plan_respects_global_killswitch(tmp_path: Path) -> None:
    root = _copy_real_configs(tmp_path)
    killswitch.set_global(True, reason="gel total S9", poles_root=root)
    plan = await plan_fleet(poles_root=root, now=NOW, dry_run=True)
    assert plan.to_launch == []
    assert all(d.verdict == "skipped_frozen" for d in plan.decisions if d.schedule)


async def test_plan_respects_daily_limit(tmp_path: Path) -> None:
    root = _copy_real_configs(tmp_path)
    (root / "fleet.yaml").write_text(
        yaml.safe_dump({"daily_limits": {"veille/trend_spotter": 1}}), encoding="utf-8"
    )
    fleet_runlog.append_fleet_run(
        fleet_runlog.FleetRun(
            at=NOW, pole="veille", script="trend_spotter", status="success", duration_ms=1.0
        ),
        poles_root=root,
    )
    plan = await plan_fleet(poles_root=root, now=NOW, dry_run=True)
    verdicts = {(d.pole, d.script): d.verdict for d in plan.decisions}
    assert verdicts[("veille", "trend_spotter")] == "skipped_daily_limit"


async def test_run_fleet_cycle_dry_run_launches_nothing(tmp_path: Path) -> None:
    root = _copy_real_configs(tmp_path)
    plan = await plan_fleet(poles_root=root, now=NOW, dry_run=True)
    result = await run_fleet_cycle(plan, poles_root=root)
    assert result.dry_run is True
    assert result.script_outcomes == []
    assert result.agent_outcomes == []


async def test_run_fleet_cycle_triggers_cron_agents(tmp_path: Path) -> None:
    """Le cycle live lance tous les scripts dûs puis réveille les agents 1-6 (cron)."""
    root = _copy_real_configs(tmp_path)
    plan = await plan_fleet(poles_root=root, now=NOW, dry_run=False, max_concurrent=4)

    ran: list[tuple[str, str]] = []
    woke: list[str] = []

    async def fake_script_runner(script: BaseScript) -> ScriptResult:
        ran.append((script.pole, script.name))
        return ScriptResult(status="success", summary="fake")

    async def fake_agent_runner(agent: BaseAgent) -> AgentResult:
        woke.append(agent.pole)
        return AgentResult(status="success", summary="fake", actions=["x"])

    result = await run_fleet_cycle(
        plan,
        poles_root=root,
        script_runner=fake_script_runner,
        agent_runner=fake_agent_runner,
        now=NOW,
    )
    assert len(result.script_outcomes) == len(plan.to_launch)
    assert len(ran) == len(plan.to_launch)
    # Agents réveillés : pôles 1-6 (trigger cron). PAS la Mémoire (trigger script),
    # PAS le SRE (aucun agent).
    assert set(woke) == {"veille", "marketing", "pub", "vente", "finance", "direction"}
    assert all(o.status == "success" for o in result.agent_outcomes)
    # Les runs ont bien été journalisés dans le journal de flotte (pas le runlog SRE).
    assert fleet_runlog.load_fleet_runs(poles_root=root)
    assert not (root / "sre" / "runlog.jsonl").exists()


async def test_run_fleet_cycle_real_runners_compose_the_chain(tmp_path: Path) -> None:
    """Cycle live, runners RÉELS (run_script + agent.run()) : le script écrit sa
    mémoire et l'agent du même pôle la relit — via le même ``poles_root``.

    On cible direction/strategy_bot (écrit un digest même flotte vide, et le
    DirectionAgent renvoie ``success`` dès qu'il voit ≥ 1 fait). Si l'orchestrateur
    passait un mauvais ``poles_root`` à l'agent, ce dernier lirait une mémoire vide
    et renverrait ``skipped`` — donc ``success`` prouve la propagation du root.
    """
    root = _copy_real_configs(tmp_path)
    plan = FleetPlan(
        decisions=[_launch("direction", "strategy_bot")],
        max_concurrent=2,
        dry_run=False,
        trigger_agents=True,
        generated_at=NOW,
    )
    result = await run_fleet_cycle(plan, poles_root=root, now=NOW)  # runners par défaut = réels
    assert any(o.pole == "direction" and o.status == "success" for o in result.script_outcomes)
    assert await memory.read_pole_memory("direction", poles_root=root)  # mémoire réelle écrite
    agent_out = [o for o in result.agent_outcomes if o.pole == "direction"]
    assert agent_out and agent_out[0].status == "success"  # agent réel réveillé sur mémoire fraîche
    # Journalisé dans le journal de flotte, pas le runlog SRE.
    assert fleet_runlog.load_fleet_runs(poles_root=root)
    assert not (root / "sre" / "runlog.jsonl").exists()


async def test_run_fleet_cycle_skipped_only_pole_does_not_wake_agent(tmp_path: Path) -> None:
    """Un pôle dont les seuls scripts ``skipped`` ne réveille pas son agent."""
    root = _copy_real_configs(tmp_path)
    plan = FleetPlan(
        decisions=[_launch("veille", "trend_spotter"), _launch("marketing", "content_bot")],
        max_concurrent=2,
        dry_run=False,
        trigger_agents=True,
        generated_at=NOW,
    )
    woke: list[str] = []

    async def runner(script: BaseScript) -> ScriptResult:
        # veille saute, marketing réussit.
        return ScriptResult(status="skipped" if script.pole == "veille" else "success")

    async def agent_runner(agent: BaseAgent) -> AgentResult:
        woke.append(agent.pole)
        return AgentResult(status="success", actions=["x"])

    await run_fleet_cycle(
        plan, poles_root=root, script_runner=runner, agent_runner=agent_runner, now=NOW
    )
    assert "marketing" in woke  # script réussi → agent réveillé
    assert "veille" not in woke  # seul script sauté → pas de réveil


async def test_run_fleet_cycle_trigger_agents_false_skips_all_agents(tmp_path: Path) -> None:
    root = _copy_real_configs(tmp_path)
    plan = await plan_fleet(poles_root=root, now=NOW, dry_run=False, trigger_agents=False)
    woke: list[str] = []

    async def runner(_: BaseScript) -> ScriptResult:
        return ScriptResult(status="success")

    async def agent_runner(agent: BaseAgent) -> AgentResult:
        woke.append(agent.pole)
        return AgentResult(status="success")

    result = await run_fleet_cycle(
        plan, poles_root=root, script_runner=runner, agent_runner=agent_runner, now=NOW
    )
    assert result.script_outcomes  # les scripts tournent
    assert result.agent_outcomes == []  # mais aucun agent
    assert woke == []


async def test_run_fleet_cycle_isolates_script_and_agent_exceptions(tmp_path: Path) -> None:
    """Un script OU un agent qui lève n'interrompt pas le cycle (pôle suivant OK)."""
    root = _copy_real_configs(tmp_path)
    plan = FleetPlan(
        decisions=[_launch("veille", "trend_spotter"), _launch("marketing", "content_bot")],
        max_concurrent=2,
        dry_run=False,
        trigger_agents=True,
        generated_at=NOW,
    )

    async def script_runner(script: BaseScript) -> ScriptResult:
        if script.pole == "veille":
            raise RuntimeError("script boom")
        return ScriptResult(status="success")

    async def agent_runner(agent: BaseAgent) -> AgentResult:
        if agent.pole == "marketing":
            raise RuntimeError("agent boom")
        return AgentResult(status="success", actions=["x"])

    result = await run_fleet_cycle(
        plan, poles_root=root, script_runner=script_runner, agent_runner=agent_runner, now=NOW
    )
    scripts = {o.pole: o for o in result.script_outcomes}
    agents = {o.pole: o for o in result.agent_outcomes}
    # Le script veille qui crashe est contenu (failed + erreur) et journalisé.
    assert scripts["veille"].status == "failed" and scripts["veille"].error
    assert scripts["marketing"].status == "success"
    journaled = {r.script: r for r in fleet_runlog.load_fleet_runs(poles_root=root)}
    assert journaled["trend_spotter"].status == "failed"
    # L'agent marketing qui crashe est contenu (failed + erreur), veille reste réveillé.
    assert agents["marketing"].status == "failed" and agents["marketing"].error
    assert agents["veille"].status == "success"


# =============================================================================
# 3. Cycle complet réel script → mémoire → agent → action, pôle par pôle
# =============================================================================
async def test_e2e_veille(tmp_path: Path) -> None:
    root = _copy_real_configs(tmp_path)
    today = datetime.now(UTC).date().isoformat()
    sources = tmp_path / "sources.yaml"
    sources.write_text(
        yaml.safe_dump(
            {
                "items": [
                    {
                        "title": "Exploitation active d'une faille VPN SSL",
                        "url": "https://cert.fr/0",
                        "published_at": today,
                        "keywords": ["vpn", "cve"],
                        "weight": 1.0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    result = await run_script(TrendSpotterScript(poles_root=root, sources_path=sources))
    assert result.status == "success"
    assert await memory.read_pole_memory("veille", poles_root=root)

    res = await VeilleAgent(poles_root=root).run()
    assert res.status == "success"
    assert res.actions


async def test_e2e_marketing(tmp_path: Path) -> None:
    root = _copy_real_configs(tmp_path)
    media = tmp_path / "media.yaml"
    media.write_text(
        yaml.safe_dump(
            {
                "contacts": [
                    {"slug": "a", "name": "A", "beat": "cyber", "email": "a@x.fr"},
                    {"slug": "b", "name": "B", "beat": "cyber"},  # email manquant → incomplet
                ]
            }
        ),
        encoding="utf-8",
    )
    result = await run_script(MediaListBuilderScript(poles_root=root, media_list_path=media))
    assert result.status == "success"
    assert await memory.read_pole_memory("marketing", poles_root=root)

    # Signal Veille cross-pôle → l'agent a de la matière éditoriale à router.
    await memory.write_memory(
        "veille",
        "breach_watcher",
        "Fuite massive chez un fournisseur cloud",
        kind="breach",
        tags=("critical",),
        poles_root=root,
    )
    res = await MarketingAgent(poles_root=root).run()
    assert res.status == "success"
    assert res.actions


async def test_e2e_pub(tmp_path: Path) -> None:
    root = _copy_real_configs(tmp_path)
    today = datetime.now(UTC).date().isoformat()
    camp = root / "pub" / "campaigns"
    camp.mkdir(parents=True, exist_ok=True)
    (camp / f"{today}-google_search.csv").write_text(
        "Campaign,Impressions,Clicks,Cost,Conversions\nGaspille,5000,250,500.00,2\n",
        encoding="utf-8",
    )
    result = await run_script(AdsOptimizerScript(poles_root=root, window_days=30))
    assert result.status == "success"
    assert await memory.read_pole_memory("pub", poles_root=root)

    res = await PubAgent(poles_root=root).run()
    assert res.status == "success"
    assert res.actions


async def test_e2e_vente(tmp_path: Path) -> None:
    root = _copy_real_configs(tmp_path)
    # bloctel_guard dégrade proprement sur entrée absente : écrit un fait neutre.
    result = await run_script(BloctelGuardScript(poles_root=root))
    assert result.status == "success"
    assert await memory.read_pole_memory("vente", poles_root=root)

    await memory.write_memory(
        "vente",
        "lead_enricher",
        "Lead qualifié Marc (RSSI Acme)",
        kind="lead",
        tags=("qualified",),
        important=True,
        poles_root=root,
    )
    res = await VenteAgent(poles_root=root).run()
    assert res.status == "success"


async def test_e2e_finance(tmp_path: Path) -> None:
    root = _copy_real_configs(tmp_path)
    # rgpd_auditor écrit un fait (gap registre) même sur entrée absente.
    result = await run_script(RGPDAuditorScript(poles_root=root))
    assert result.status == "success"
    assert await memory.read_pole_memory("finance", poles_root=root)

    await memory.write_memory(
        "finance",
        "finance_bot",
        "Relance J+15 facture in1",
        kind="dunning",
        tags=("J+15",),
        important=True,
        poles_root=root,
    )
    await memory.write_memory(
        "vente",
        "proposal_bot",
        "Devis DEAL-1 (Acme) sent",
        kind="proposal",
        tags=("sent",),
        poles_root=root,
    )
    res = await FinanceAgent(poles_root=root).run()
    assert res.status == "success"
    assert "vente" in (res.summary or "")  # lecture cross-pôle effective


async def test_e2e_direction(tmp_path: Path) -> None:
    root = _copy_real_configs(tmp_path)
    # strategy_bot écrit un digest même flotte vide.
    result = await run_script(StrategyBotScript(poles_root=root))
    assert result.status == "success"
    assert await memory.read_pole_memory("direction", poles_root=root)

    await memory.write_memory(
        "veille",
        "trend_spotter",
        "5 sujets cyber chauds détectés",
        kind="signal",
        tags=("cyber",),
        poles_root=root,
    )
    res = await DirectionAgent(poles_root=root).run()
    assert res.status == "success"
    assert "veille" in (res.summary or "")  # lecture cross-pôle « * » effective


async def test_e2e_memoire(tmp_path: Path) -> None:
    root = _copy_real_configs(tmp_path)
    # capability_router audite le câblage réel (copié) → fait wiring-audit.
    result = await run_script(CapabilityRouterScript(poles_root=root))
    assert result.status == "success"
    assert await memory.read_pole_memory("memoire", poles_root=root)

    # Un fait veille périmé → l'agent Mémoire propose de le supprimer (jamais lui-même).
    await memory.write_memory(
        "veille", "trend_spotter", "signal périmé", created_at=OLD, poles_root=root
    )
    policy = MemoryPolicy(active_for=("veille",), default_ttl_days=180)
    res = await MemoireAgent("veille", poles_root=root, policy=policy, now=NOW).run()
    assert res.status == "success"
    assert res.actions  # ≥ 1 candidat safe-to-delete


async def test_e2e_sre(tmp_path: Path) -> None:
    root = _copy_real_configs(tmp_path)
    # SRE = aucun agent : le cycle déterministe est script → mémoire (+ runlog SRE).
    result = await run_script(BotConfigManagerScript(poles_root=root))
    assert result.status == "success"
    assert await memory.read_pole_memory("sre", poles_root=root)
