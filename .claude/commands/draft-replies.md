---
description: Lance ReplyBot — drafte des réponses aux mentions LinkedIn / Mastodon pending dans data/social/mentions.yaml. Pas de publish auto.
---

# /draft-replies

Cap journalier 10 réponses. Drafts dans `data/social/reply_drafts/<id>.md`.

```python
from argos_ops.agents.base import run_agent
from argos_ops.agents.reply_bot import ReplyBot

result = await run_agent(ReplyBot())
print(result.status, result.output_summary)
```

## Format `data/social/mentions.yaml`

```yaml
mentions:
  - id: linkedin-abc123
    platform: linkedin
    author: Marie Durand
    mention_url: https://www.linkedin.com/feed/update/...
    original_text: "Vraiment intéressant le scan Argos sur les dépendances npm."
    sentiment: positive
    status: pending
```

## Sortie

- `data/social/reply_drafts/<id>.md` avec frontmatter + draft réponse
- Le ton est adapté au `sentiment` (positive / neutral / negative)
- Publish manuel : copy/paste sur la plateforme par le founder
