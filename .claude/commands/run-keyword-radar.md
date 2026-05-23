---
description: Lance KeywordRadar — diff positions SERP haute priorité vs historique, écrit data/seo/movements-<date>.md. Alerte Discord si ≥ 3 pertes > 5 positions.
---

# /run-keyword-radar

Hebdo (lundi matin). Compare `data/seo/keywords_tracked.yaml` vs
`data/seo/ranks_history.yaml`.

```python
from argos_ops.agents.base import run_agent
from argos_ops.agents.keyword_radar import KeywordRadar

result = await run_agent(KeywordRadar())
print(result.status, result.output_summary)
```

## Format keywords_tracked.yaml

```yaml
keywords:
  - term: "pentest PME"
    position: 12
    priority: high
  - term: "audit cybersécurité"
    position: 28
    priority: high
```

Le bot écrit `data/seo/ranks_history.yaml` après chaque run (overwrite)
pour servir de baseline au run suivant.

## Sortie

- Digest `data/seo/movements-YYYY-MM-DD.md` (top 5 montées / descentes)
- Notif jaune Discord si ≥ 3 keywords perdent > 5 positions
