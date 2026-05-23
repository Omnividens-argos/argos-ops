---
description: Lance MediaListBuilder — audit hebdo de data/comm/media_list.yaml (journalistes cyber). Alerte sur fiches incomplètes ou DB sous le seuil 10 contacts.
---

# /run-media-list-build

```python
from argos_ops.agents.base import run_agent
from argos_ops.agents.media_list_builder import MediaListBuilder

result = await run_agent(MediaListBuilder())
print(result.status, result.output_summary)
```

## Format `data/comm/media_list.yaml`

```yaml
contacts:
  - slug: korben
    name: Korben
    outlet: korben.info
    beat: cyber
    email: contact@korben.info
    twitter: "@korben"
    last_interaction: 2026-04-10
```

## Sortie

- Récap par beat (cyber / startup / business / tech)
- Liste des fiches incomplètes (email ou beat manquant)
- Alerte Discord si signal (incomplètes ou DB < 10 contacts)
