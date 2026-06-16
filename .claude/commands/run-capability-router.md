---
description: Lance CapabilityRouter — audite le câblage inter-agents (data/agent_capabilities.yaml + graphe d'accès) et alerte sur règles orphelines, câblages à vide, write_back actifs. Read-only, silence Discord si sain.
---

# /run-capability-router

Slash command pour `CapabilityRouter` (P21, file-based — cf.
[D-033](../../docs/DECISIONS.md)). Audite le **câblage inter-agents** : quels
bots ont le droit de consommer la mémoire de quels autres, avec quels filtres.

## Procédure

```python
from argos_ops.agents.base import run_agent
from argos_ops.agents.capability_router import CapabilityRouter

result = await run_agent(CapabilityRouter())
print(result.status, result.output_summary)
```

## Ce qu'il vérifie

- **Règle orpheline** : `subject`/`object` d'une règle n'est pas un agent connu
  de la flotte (graphe d'accès ou mémoire) → typo ou bot supprimé.
- **Câblage à vide** : une règle `read` pointe un object dont la mémoire ne
  contient aucun fait matchant les filtres → câblage déclaré mais inerte.
- **write_back actif** : signalé (risque comportemental — boucle douce A→B→A).

## Câblage

- Règles : [`data/agent_capabilities.yaml`](../../data/agent_capabilities.yaml)
- Module runtime : `argos_ops.capabilities` (`consume_capabilities`, `write_back`)
- Consommé par l'orchestrateur (`_consume_capabilities`) et chaque bot qui en a
  besoin au début de son `run()`.

## Sortie

- Embed Discord jaune sur `DISCORD_WEBHOOK_OPS_LOGS` si anomalies, **silence**
  si le câblage est sain.
- Cadence cron : hebdo (lundi 05:45) via `setup_watchers_tasks.ps1`.
