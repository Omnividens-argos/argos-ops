---
description: Lance CrisisCommBot — drafte une réponse type pour chaque incident ouvert dans data/comm/crisis_incidents.yaml. Templates par incident_type.
---

# /draft-crisis-response

```python
from argos_ops.agents.base import run_agent
from argos_ops.agents.crisis_comm import CrisisCommBot

result = await run_agent(CrisisCommBot())
print(result.status, result.output_summary)
```

## Types d'incidents reconnus

- `data_breach` — fuite de données (template inclut le délai CNIL 72h)
- `service_down` — indisponibilité service
- `false_finding_dispute` — finding contesté par un client
- `negative_press` — article négatif

## Format `data/comm/crisis_incidents.yaml`

```yaml
incidents:
  - id: 2026-05-23-degraded-api
    incident_type: service_down
    severity: major
    scope: API publique
    time: "2026-05-23 14h Paris"
    notes: ...
    status: open
```

## Sortie

`data/comm/crisis_drafts/<incident_id>.md` avec template appliqué +
checklist post-publication (CNIL, clients impactés, etc).

Discord rouge si ≥ 1 incident `severity: critical` est `open`.
