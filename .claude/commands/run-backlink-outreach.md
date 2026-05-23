---
description: Lance BacklinkOutreach — drafte des cold emails pour échanges de liens depuis data/seo/backlink_targets.yaml. Pas d'envoi auto, humain-in-the-loop.
---

# /run-backlink-outreach

Drafte jusqu'à 5 cold emails / run pour des cibles `status: queued` dans
`data/seo/backlink_targets.yaml`. Drafts dans `data/seo/backlink_drafts/<slug>.md`.

## Procédure

```python
from argos_ops.agents.base import run_agent
from argos_ops.agents.backlink_outreach import BacklinkOutreach

result = await run_agent(BacklinkOutreach())
print(result.status, result.output_summary)
```

## Format `data/seo/backlink_targets.yaml`

```yaml
targets:
  - slug: korben-blog
    site_url: https://korben.info
    contact_email: contact@korben.info
    angle: ressource invitée pentest PME
    status: queued
```

Envoi : copy/paste depuis les drafts via skill `zimbra-ops` après
relecture founder.