---
description: Lance WebinarPromoter — drafte 3 posts sociaux (J-14/J-7/J-1) + email teaser + fiche replay pour chaque webinar dans les 14 jours à venir.
---

# /promote-webinar

```python
from argos_ops.agents.base import run_agent
from argos_ops.agents.webinar_promoter import WebinarPromoter

result = await run_agent(WebinarPromoter())
print(result.status, result.output_summary)
```

## Format `data/webinars/upcoming.yaml`

```yaml
webinars:
  - slug: 2026-06-pentest-supply-chain
    title: Pentest PME — supply chain et SBOM
    date: 2026-06-15
    register_url: https://omnividens.fr/webinars/2026-06
    speaker: Founder Argos
    description: Webinar 45 min sur la chaîne d'approvisionnement logicielle...
```

## Sortie

- 3 drafts sociaux dans `data/content/drafts/webinar-<slug>-j{14,7,1}.md`
  (channel: linkedin par défaut, à ajuster manuellement avant /publish-content)
- `data/webinars/<slug>/email_teaser.md` + `replay_edit.md`
- Idempotent : ne réécrit pas les drafts existants

Le scheduling (timestamps) est à compléter manuellement via skill
`content-scheduler`.
