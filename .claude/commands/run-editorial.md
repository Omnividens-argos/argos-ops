---
description: Lance EditorialBot — lit le dernier digest TrendSpotter et écrit une queue de recommandations (writer + canal + angle par sujet chaud) dans data/editorial/queue-<date>.yaml. Ne lance aucun writer ; le fondateur exécute ensuite les /draft-* listés.
---

# /run-editorial

Slash command pour **EditorialBot**, le chef d'orchestre éditorial. Il lit le
dernier digest TrendSpotter (`data/trends/digest-<date>.md`) et, pour chaque
sujet cyber chaud, **recommande un canal + un angle**, puis écrit la liste de
tâches dans `data/editorial/queue-<date>.yaml`.

> **Mode shadow** : EditorialBot **ne drafte pas** lui-même. Il recommande
> quels `/draft-*` lancer. Le fondateur garde la main (humain-in-the-loop).

## Procédure

```python
from argos_ops.agents.base import run_agent
from argos_ops.agents.editorial_bot import EditorialBot

result = await run_agent(EditorialBot())
print(result.status, result.output_summary)
```

Ou en CLI : `uv run python scripts/run_editorial.py`.

## Répartition des canaux

- Sujet **grand public** (phishing, ransomware, mot de passe, sauvegarde…)
  → **Meta** (persona TPE/PME, `meta-writer`).
- Autres sujets → round-robin **LinkedIn / Mastodon / Bluesky / X** (évite de
  tout concentrer sur un canal).
- **Truth Social exclu** par défaut (canal expérimental + brand safety
  apolitique → mauvais fit pour un sujet chaud arbitraire).

## Sortie attendue

- `output_summary="digest=yes tasks=K"` (ou `digest=none tasks=0` si aucun
  digest TrendSpotter trouvé).
- Fichier `data/editorial/queue-<date>.yaml` créé si ≥ 1 tâche.
- Notif Discord (`DISCORD_WEBHOOK_CONTENT` ou `OPS_LOGS`) uniquement si ≥ 1
  tâche (silence sinon).

## Format `data/editorial/queue-<date>.yaml`

```yaml
generated_at: "2026-06-02T08:00:00+00:00"
source_digest: digest-2026-06-02.md
mode: shadow
tasks:
  - topic: "Faille critique sur Ivanti EPM"
    channel: linkedin
    writer: linkedin-writer
    slash: /draft-linkedin
    angle: "Angle décideur : relier le sujet à une objection RSSI/CTO, CTA soft."
```

## Workflow

1. TrendSpotter tourne (`/run-trend-spot`) → écrit le digest.
2. `/run-editorial` → lit le digest, écrit la queue de recommandations.
3. Le fondateur ouvre la queue et lance les `/draft-*` recommandés (un par
   sujet/canal), chacun humain-in-the-loop avec audit `claude-judge`.

## Liens

- Agent : [`argos_ops/agents/editorial_bot.py`](../../argos_ops/agents/editorial_bot.py)
- Runner : [`scripts/run_editorial.py`](../../scripts/run_editorial.py)
- Queue : `data/editorial/` (cf. son README)
- Amont : TrendSpotter (`/run-trend-spot`) · Aval : writers `/draft-*`
