---
description: Lance NewsletterBot — drafte la newsletter mensuelle depuis data/blog/index.yaml + digests TrendSpotter. Humain-in-the-loop pour validation + envoi via zimbra-ops.
---

# /draft-newsletter

Slash command mensuel (1er mardi du mois) pour NewsletterBot.

## Procédure

```python
from argos_ops.agents.base import run_agent
from argos_ops.agents.newsletter_bot import NewsletterBot

result = await run_agent(NewsletterBot())
print(result.status, result.output_summary)
```

## Sortie

- Draft créé sous `data/newsletters/drafts/YYYY-MM.md` (frontmatter
  `status: draft`)
- `output_summary="month=2026-05 blog=4 trends=14"`
- Notif Discord avec lien vers le draft

## Validation manuelle (founder)

Le founder relit le draft, complète la section "Côté Argos", puis envoie
la newsletter via skill `zimbra-ops` ou un service tiers (si choisi
plus tard).