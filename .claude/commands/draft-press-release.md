---
description: Lance PressReleaseDrafter — drafte un communiqué de presse structuré depuis data/comm/press_releases/queue.yaml. Humain-in-the-loop pour validation.
---

# /draft-press-release

```python
from argos_ops.agents.base import run_agent
from argos_ops.agents.press_release_drafter import PressReleaseDrafter

result = await run_agent(PressReleaseDrafter())
print(result.status, result.output_summary)
```

## Format `data/comm/press_releases/queue.yaml`

```yaml
releases:
  - slug: 2026-06-launch-supply-chain
    title: Argos lance son module supply chain
    angle: product
    summary: Nouveau scan dépendances + SBOM pour PME tech.
    body: |
      Argos étend son scan avec un module dédié supply chain...
    founder_quote: Notre conviction est que la chaîne de dépendances est le maillon faible des PME.
    status: queued
```

## Sortie

`data/comm/press_releases/<slug>.md` au format canonique :
contexte / citation / boilerplate / contacts. Le founder relit et envoie
aux journalistes via la `media_list.yaml`.
