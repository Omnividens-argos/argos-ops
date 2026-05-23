---
description: Lance BrandGuardBot — audit brand consistency (tagline, domaine omnividens.fr, AI Act disclosure, anti-FUD) sur tous les drafts sortants.
---

# /run-brand-audit

```python
from argos_ops.agents.base import run_agent
from argos_ops.agents.brand_guard import BrandGuardBot

result = await run_agent(BrandGuardBot())
print(result.status, result.output_summary)
```

## Périmètre

Scan récursif des `.md` dans :
- `data/content/drafts/`
- `data/newsletters/drafts/`
- `data/comm/press_releases/`
- `data/marketing/case_studies/`
- `data/marketing/testimonial_drafts/`
- `data/seo/backlink_drafts/`

## Règles canoniques appliquées

Voir [argos_ops/comm/brand.py](../../argos_ops/comm/brand.py) :
- **error** : `omnividens.com` au lieu de `.fr`
- **error** : « validé par humain » (non-vérifiable, contre AI Act)
- **warning** : `argos` ou `omnividens` non capitalisés
- **warning** : mots FUD (catastrophe, apocalyptique, terriblement)

## Sortie

- Digest `data/comm/brand_audits/<date>.md` avec issues par fichier
- Discord rouge si ≥ 1 error, jaune si ≥ 1 warning, vert sinon

Ne modifie aucun draft — c'est au founder de corriger.
