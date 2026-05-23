---
description: Lance TestimonialHunter — drafte les demandes de verbatim post-NPS pour les promoteurs (score ≥ 9) dans data/crm/nps_responses.yaml.
---

# /draft-testimonial-request

Cap journalier 5 demandes. Drafts dans `data/marketing/testimonial_drafts/<slug>.md`.

```python
from argos_ops.agents.base import run_agent
from argos_ops.agents.testimonial_hunter import TestimonialHunter

result = await run_agent(TestimonialHunter())
print(result.status, result.output_summary)
```

## Format `data/crm/nps_responses.yaml`

```yaml
responses:
  - slug: acme-jdupont
    contact_name: Julien Dupont
    contact_email: jdupont@acme.fr
    company: Acme SAS
    score: 9
    comment: "Pentest livré en 3 jours, vraiment efficace."
```

## Envoi

Manuellement via skill `zimbra-ops` après relecture founder. La demande
inclut un opt-in explicite avant publication.
