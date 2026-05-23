---
description: Lance SpokespersonPrep — drafte un Q&A brief (5 questions probables + stats + no-go) pour chaque interview à venir dans les 7 jours.
---

# /prep-interview

```python
from argos_ops.agents.base import run_agent
from argos_ops.agents.spokesperson_prep import SpokespersonPrep

result = await run_agent(SpokespersonPrep())
print(result.status, result.output_summary)
```

## Format `data/comm/interviews/upcoming.yaml`

```yaml
interviews:
  - slug: 2026-06-zdnet
    outlet: ZDNet France
    journalist: Marie Durand
    date: 2026-06-15
    beat: cyber
    duration_minutes: 45
```

## Sortie

`data/comm/interviews/<slug>/qa_brief.md` avec :
- 5 questions probables (selon `beat`)
- Stats clés depuis `data/comm/founder_stats.yaml`
- 4 no-go topics canoniques
- Checklist post-interview (bon à tirer, date pub, ajout à press_mentions)

Le founder personnalise les réponses avant le RDV.
