# PROMPT-3 Session — P22.E Compliance Sprint 8 + Direction Sprint 9

> Session 3 de 4 prompts parallèles (P22.E). Branche locale
> `feat/p22e-compliance-direction-9-bots`. Zéro push.
> Worktree dédié : `argos-ops-p22e/` (pour isoler des sessions sœurs).

## Livrables — 9 nouveaux bots

### Compliance (Sprint 8) — 5 bots

| Bot | Rôle équiv. | Slash | Fichier |
|-----|-------------|-------|---------|
| RGPDAuditor | DPO | `/run-rgpd-audit` | [`argos_ops/agents/rgpd_auditor.py`](../../argos_ops/agents/rgpd_auditor.py) |
| AIActComplianceBot | AI Compliance Officer | `/run-ai-act-audit` | [`argos_ops/agents/ai_act_compliance.py`](../../argos_ops/agents/ai_act_compliance.py) |
| BloctelGuard | Compliance Bloctel | _(cron pur)_ | [`argos_ops/agents/bloctel_guard.py`](../../argos_ops/agents/bloctel_guard.py) |
| ContractDeadlineBot | Legal Ops | `/run-contract-deadlines` | [`argos_ops/agents/contract_deadline.py`](../../argos_ops/agents/contract_deadline.py) |
| IncidentLogger | RSSI | `/log-incident` | [`argos_ops/agents/incident_logger.py`](../../argos_ops/agents/incident_logger.py) |

### Direction (Sprint 9) — 4 bots

| Bot | Rôle équiv. | Slash | Fichier |
|-----|-------------|-------|---------|
| StrategyBot | VP Stratégie | `/run-strategy-digest` | [`argos_ops/agents/strategy_bot.py`](../../argos_ops/agents/strategy_bot.py) |
| OKRTracker | Chief of Staff | `/run-okr-review` | [`argos_ops/agents/okr_tracker.py`](../../argos_ops/agents/okr_tracker.py) |
| BoardReporter | Investor Relations | `/run-board-pack` | [`argos_ops/agents/board_reporter.py`](../../argos_ops/agents/board_reporter.py) |
| DecisionLogger | Knowledge Steward | `/log-decision` | [`argos_ops/agents/decision_logger.py`](../../argos_ops/agents/decision_logger.py) |

## Extension `argos_ops/compliance.py`

P17 (1 check) → P22.E (7 checks). Ajouts :

- `scan_pii_collectors(path)` — regex sur fichiers Python : email, phone,
  ip_address, name, address, id_card
- `classify_ai_act_risk(raw)` — normalise vers `minimal` / `limited` /
  `high` / `prohibited` / `unclassified`
- `normalize_phone_fr(raw)` — canonicalise au format `+33XXXXXXXXX`
- `is_phone_on_bloctel(phone, list_path)` — match contre liste mensuelle
- `next_renewal_date(start, term_months, today)` — projection sur le
  prochain anniversaire de contrat (gère wrap année + mois courts)
- `days_until(target, today)` — signed delta jours

Tous **déterministes** (zéro LLM) et **conservateurs**.

## Patterns réutilisés

- 7 bots sur 9 héritent de `BaseAgent` + utilisent
  `argos_ops.agents._watcher_base.emit_alert_or_silence` (silence si vert)
- `IncidentLogger` et `DecisionLogger` sont des **agents interactifs**
  (slash collecte inputs → appelle fonction pure idempotente)
- `StrategyBot` et `BoardReporter` lisent `agent_runs` via `session_scope`
- `BoardReporter` réutilise `sum_active_mrr_eur` (FinanceBot source de
  vérité, skill `stripe-ops` indirect)
- Chaque agent expose `ai_act_risk_class` (tous `minimal` ou `limited`,
  testé par AIActComplianceBot)

## Tests

| Fichier | # tests |
|---------|---------|
| [`tests/test_compliance_p22e.py`](../../tests/test_compliance_p22e.py) | 24 |
| [`tests/test_rgpd_auditor.py`](../../tests/test_rgpd_auditor.py) | 10 |
| [`tests/test_ai_act_compliance.py`](../../tests/test_ai_act_compliance.py) | 6 |
| [`tests/test_bloctel_guard.py`](../../tests/test_bloctel_guard.py) | 10 |
| [`tests/test_contract_deadline.py`](../../tests/test_contract_deadline.py) | 9 |
| [`tests/test_incident_logger.py`](../../tests/test_incident_logger.py) | 8 |
| [`tests/test_strategy_bot.py`](../../tests/test_strategy_bot.py) | 6 |
| [`tests/test_okr_tracker.py`](../../tests/test_okr_tracker.py) | 13 |
| [`tests/test_board_reporter.py`](../../tests/test_board_reporter.py) | 7 |
| [`tests/test_decision_logger.py`](../../tests/test_decision_logger.py) | 7 |
| **Total** | **100** |

**Garde-fou DecisionLogger** : aucun test n'écrit le vrai
`docs/DECISIONS.md` — tous passent un `output_path` dans `tmp_path`.

## Données livrées

- `data/compliance/rgpd_registry.example.yaml` — template registre RGPD
- `data/compliance/bloctel/.gitkeep` — convention de nommage
- `data/compliance/incidents/.gitkeep` — convention de nommage
- `data/contracts/clients.example.yaml` — template contrats
- `data/okr/2026-Q2.example.yaml` — template OKRs trimestriels
- `data/strategy/burn.example.yaml` — template burn / runway

**Aucun secret committé.** Le fichier réel `burn.yaml` reste à
gitignorer en prod, comme `clients.yaml` (noms clients confidentiels).

## Annexe D — checkboxes cochées

- §1 Direction & Stratégie : 4/4 lignes `[x] ✅`
- §9 Juridique & Compliance : 5/5 lignes `[x] ✅`
- Compteur tête : ✅ 17 → ✅ 26 ; ⬜ 59 → ⬜ 50 (+9 livrés, total cible
  inchangé à 79)

## agentCatalog.ts — 9 cartes flip de `roadmap` → `active`

`status: "active"` + `name: "<BotName>"` (clé matching API) + `roadmapRef`
mis à jour à `P22.E livré 2026-05-23`.

## Slash commands installées

- `/run-rgpd-audit`
- `/run-ai-act-audit`
- `/run-contract-deadlines`
- `/log-incident` (interactif)
- `/run-strategy-digest`
- `/run-okr-review`
- `/run-board-pack`
- `/log-decision` (interactif)
- _(BloctelGuard = cron pur, pas de slash)_

## Commits attendus

Branche : `feat/p22e-compliance-direction-9-bots` (worktree
`../argos-ops-p22e`)

1. `feat(p22e): Compliance Sprint 8 — 5 bots + compliance.py extension`
   - argos_ops/compliance.py (extension P22.E)
   - argos_ops/agents/{rgpd_auditor,ai_act_compliance,bloctel_guard,
     contract_deadline,incident_logger}.py
   - tests/{test_compliance_p22e,test_rgpd_auditor,test_ai_act_compliance,
     test_bloctel_guard,test_contract_deadline,test_incident_logger}.py
   - scripts/run_{rgpd_auditor,ai_act_compliance,bloctel_guard,
     contract_deadlines,incident_logger}.py
   - .claude/commands/{run-rgpd-audit,run-ai-act-audit,run-contract-deadlines,
     log-incident}.md
   - data/compliance/{rgpd_registry.example.yaml,bloctel/.gitkeep,
     incidents/.gitkeep}
   - data/contracts/clients.example.yaml

2. `feat(p22e): Direction Sprint 9 — 4 bots + Annexe D + catalog`
   - argos_ops/agents/{strategy_bot,okr_tracker,board_reporter,
     decision_logger}.py
   - tests/{test_strategy_bot,test_okr_tracker,test_board_reporter,
     test_decision_logger}.py
   - scripts/run_{strategy_bot,okr_tracker,board_reporter,
     decision_logger}.py
   - .claude/commands/{run-strategy-digest,run-okr-review,run-board-pack,
     log-decision}.md
   - data/okr/2026-Q2.example.yaml
   - data/strategy/burn.example.yaml
   - docs/ARGOS_OPS_PLAN.md (Annexe D §1 + §9 + compteur)
   - argos_ops/ops_dashboard/frontend/src/lib/agentCatalog.ts (9 lignes)
   - data/p22-sessions/PROMPT-3-summary.md

## Non touché (volontaire)

- `CLAUDE.md` (stable, l'autre section dit que CLAUDE.md ne porte plus
  l'avancement bots)
- Autres lignes de l'Annexe D (autres services / sprints)
- Le vrai `docs/DECISIONS.md` (DecisionLogger n'y écrit qu'en runtime
  via `/log-decision`, jamais depuis un test)
- Les autres prompts P22.x parallèles (worktree isolé)
