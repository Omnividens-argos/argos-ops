# Fleet Memory — index global

> Mémoire de flotte Argos Ops (Cockpit LOT 1). **1 dossier par bot**, clé =
> `agent_name` canonique (cf. `agentCatalog.ts`). **1 fait = 1 fichier**
> `<AgentName>/facts/<fact_id>.md`. Helper : [`argos_ops/fleet_memory.py`](../../argos_ops/fleet_memory.py).
>
> Le « IN » d'un bot = sa propre mémoire ∪ la mémoire des bots qu'il peut lire
> (graphe ci-dessous). Cycle de vie (archivage / dédup / TTL / suppression) =
> futur **MemoryCurator** (P20). Aucune valeur secrète ici — faits métier only.

## Bots avec mémoire

- [EmailBot](EmailBot/INDEX.md) — signaux leads & objections extraits de l'inbox
- [LeadEnricher](LeadEnricher/INDEX.md) — fiches ICP / BANT enrichies
- [TrendSpotter](TrendSpotter/INDEX.md) — sujets cyber chauds détectés

## Graphe d'accès (qui lit qui)

> Format : `bot: [bots dont il peut LIRE la mémoire, en plus de la sienne]`.
> Un bot **absent** de ce graphe ne voit **que** sa propre mémoire.
> `"*"` = toute la flotte (réservé orchestrateur / curator).

<!-- fleet-access-graph:start -->
```yaml
# Sales : l'outbound s'appuie sur l'enrichissement + les tendances chaudes.
OutboundBot: [LeadEnricher, TrendSpotter]
# Marketing : le contenu suit les tendances détectées.
ContentBot: [TrendSpotter]
EditorialBot: [TrendSpotter]
# Meta-Ops : vision flotte complète.
OrchestratorBot: ["*"]
MemoryCurator: ["*"]
```
<!-- fleet-access-graph:end -->
