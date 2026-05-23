---
description: Lance ContentBot — publie les drafts validés (status=validated, scheduled_for <= now) sur LinkedIn / Mastodon. Shadow si tokens absents (D-024 / D-025).
---

# /publish-content

Slash command cron-friendly pour ContentBot full (P9). Scanne
`data/content/drafts/`, dispatch les drafts validés vers le bon
connecteur via `argos_ops.social.publisher`, et déplace les drafts
publiés dans `data/content/published/`.

## Préconditions

- `data/content/drafts/<slug>.md` avec frontmatter ``status: validated``
  + ``scheduled_for: 2026-05-23T08:30:00Z`` + ``channel: linkedin|mastodon``
- Au moins un webhook Discord (`DISCORD_WEBHOOK_CONTENT` ou
  `DISCORD_WEBHOOK_OPS_LOGS`) pour le récap

Tokens API optionnels — sans eux, ContentBot tourne en shadow et déplace
quand même les drafts vers `data/content/published/` avec
``status: published_shadow``.

## Procédure

```python
from argos_ops.agents.base import run_agent
from argos_ops.agents.content_bot import ContentBot

result = await run_agent(ContentBot())
print(result.status, result.output_summary)
```

## Sortie attendue

`output_summary="ready=N live=K shadow=M skipped=0 failures=0"`. Cap
journalier `CONTENT_DAILY_MAX_PER_CHANNEL` (défaut 3) appliqué par canal.

## Cron

Toutes les 2 h en journée. `content-scheduler` skill range déjà les
drafts dans la fenêtre d'engagement par canal.
