---
description: Lance LandingOptimizer — propose 3 hypothèses A/B chiffrées par page depuis data/analytics/landing_perf.yaml.
---

# /run-landing-optim

Hebdo. Lit `data/analytics/landing_perf.yaml` (alimenté depuis Umami /
Plausible) et propose des hypothèses A/B selon des seuils canoniques
(CR < 1%, bounce > 70%, time < 20s).

```python
from argos_ops.agents.base import run_agent
from argos_ops.agents.landing_optimizer import LandingOptimizer

result = await run_agent(LandingOptimizer())
print(result.status, result.output_summary)
```

## Format landing_perf.yaml

```yaml
pages:
  - page: /
    visits: 1200
    conversions: 8
    bounce_rate: 0.72
    avg_time_seconds: 18.0
```

## Sortie

- Digest `data/analytics/landing_proposals-<date>.md`
- Notif jaune Discord si ≥ 1 hypothèse générée

Le founder choisit les expériences à lancer et les déploie côté front
manuellement (pas d'outil A/B branché à ce stade).