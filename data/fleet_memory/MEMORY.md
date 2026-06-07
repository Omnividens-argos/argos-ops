# Fleet Memory — index global

> Mémoire de flotte Argos Ops (Cockpit). **1 dossier par bot**, clé =
> `agent_name` canonique (cf. `agentCatalog.ts`). **1 fait = 1 fichier**
> `<AgentName>/facts/<fact_id>.md`. Helper : [`argos_ops/fleet_memory.py`](../../argos_ops/fleet_memory.py).
>
> **Comme une mémoire de cerveau** : chaque bot *se souvient* (écrit ses faits
> en fin de run via `RunResult.extras["fleet_facts"]`), et ces souvenirs sont
> **conservés** et **prêts à l'emploi**. **Tout le monde n'y a pas accès** —
> seuls les bots qui en ont l'utilité (pour agir, décider ou produire du
> contenu) la lisent, selon le graphe ci-dessous.
>
> Cycle de vie (archivage / dédup / TTL / suppression) = **MemoryCurator** (P20).
> Aucune valeur secrète ni PII ici — faits métier only.

## Bots avec mémoire (exemples seedés)

- [EmailBot](EmailBot/INDEX.md) — signaux leads & objections extraits de l'inbox
- [LeadEnricher](LeadEnricher/INDEX.md) — fiches ICP / BANT enrichies
- [TrendSpotter](TrendSpotter/INDEX.md) — sujets cyber chauds détectés

> Les autres dossiers se créent automatiquement dès qu'un bot se souvient de
> son premier fait. Les bots cités comme **cibles** dans le graphe mais sans
> mémoire encore renvoient simplement une mémoire vide.

## Graphe d'accès (qui lit qui)

> Format : `bot: [bots dont il peut LIRE la mémoire, en plus de la sienne]`.
> Un bot **absent** de ce graphe ne voit **que** sa propre mémoire.
> `"*"` = toute la flotte (réservé direction / orchestration / curator).
> C'est le « câblage neuronal » : chaque arête existe parce que la mémoire
> source **sert** réellement au bot lecteur.

<!-- fleet-access-graph:start -->
```yaml
# ── Marketing / Contenu : a besoin des tendances + veille concurrentielle ──
ContentBot: [TrendSpotter, CompetitorWatcher, KeywordRadar]
EditorialBot: [TrendSpotter, CompetitorWatcher, FeedbackAggregator]
SEOBot: [TrendSpotter, KeywordRadar, CompetitorWatcher]
NewsletterBot: [TrendSpotter, CompetitorWatcher]
LinkedInWriter: [TrendSpotter]
MastodonWriter: [TrendSpotter]
BlueskyWriter: [TrendSpotter]
MetaWriter: [TrendSpotter]
XWriter: [TrendSpotter]

# ── Sales : a besoin de l'enrichissement et des signaux d'intention ──
OutboundBot: [LeadEnricher, IntentSignalsBot]
ProspectMiner: [IntentSignalsBot]
DealRiskScorer: [LeadEnricher, IntentSignalsBot]
DemoFollowupBot: [LeadEnricher]
ProposalBot: [LeadEnricher]

# ── Customer Success : a besoin des scores de santé et du feedback ──
ChurnPredictor: [HealthScoreBot, FeedbackAggregator]
UpsellSpotter: [HealthScoreBot]

# ── Direction / Meta-Ops : vision flotte complète ──
StrategyBot: ["*"]
OrchestratorBot: ["*"]
MemoryCurator: ["*"]
```
<!-- fleet-access-graph:end -->
