---
description: Lance TrendSpotter — détecte les sujets cyber chauds (fenêtre 14j) à partir de data/trends/sources.yaml et écrit un digest top-5 pour /draft-content et /generate-seo-brief.
---

# /run-trend-spot

Slash command quotidien pour TrendSpotter. Lit
`data/trends/sources.yaml`, score les items (récence × poids), garde la
fenêtre 14 jours, écrit le digest dans `data/trends/digest-YYYY-MM-DD.md`.

## Procédure

```python
from argos_ops.agents.base import run_agent
from argos_ops.agents.trend_spotter import TrendSpotter

result = await run_agent(TrendSpotter())
print(result.status, result.output_summary)
```

## Sortie attendue

- `output_summary="fresh=N top=K"`
- Fichier digest créé si top non vide
- Notif Discord uniquement si top non vide (silence sinon)

## Format `data/trends/sources.yaml`

```yaml
items:
  - title: "Faille critique sur Ivanti EPM"
    url: "https://cert.fr/..."
    published_at: "2026-05-22"
    keywords: [ivanti, cve, supply-chain]
    weight: 1.0
```

Maintenu à la main par le founder via veille CERT-FR / Bleeping / ANSSI
tant qu'un scraper dédié n'est pas branché.
