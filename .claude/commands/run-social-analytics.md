---
description: Lance SocialAnalytics — agrège l'engagement social (LinkedIn / Mastodon) sur 7j et alerte (jaune) si CTR < 1% ou ER < 2% en moyenne par canal.
---

# /run-social-analytics

Slash command hebdo pour SocialAnalytics. Lit
`data/social/engagement.yaml` (export manuel ou API analytics),
agrège par canal sur 7j et push un récap Discord.

## Procédure

```python
from argos_ops.agents.base import run_agent
from argos_ops.agents.social_analytics import SocialAnalytics

result = await run_agent(SocialAnalytics())
print(result.status, result.output_summary)
```

## Sortie attendue

- `output_summary="linkedin: 4posts ctr=2.1% | mastodon: 3posts ctr=0.9%"`
- Embed Discord vert si tous les canaux > seuils, jaune sinon
- Silence Discord si aucune mesure dans la fenêtre

## Format `data/social/engagement.yaml`

```yaml
posts:
  - posted_at: "2026-05-15T08:30:00Z"
    platform: linkedin
    url: "https://linkedin.com/feed/update/..."
    impressions: 1240
    engagements: 87
    clicks: 12
```

Tant que les tokens analytics LinkedIn / Mastodon ne sont pas branchés,
le YAML est alimenté manuellement (export CSV converti). Quand les
tokens existent (D-024 / D-025), un fetch hebdo automatique est
ajouté.
