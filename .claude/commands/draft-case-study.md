---
description: Lance CaseStudyDrafter — drafte le squelette d'une case study depuis data/crm/case_study_candidates.yaml (statut ready). Idempotent.
---

# /draft-case-study

```python
from argos_ops.agents.base import run_agent
from argos_ops.agents.case_study_drafter import CaseStudyDrafter

result = await run_agent(CaseStudyDrafter())
print(result.status, result.output_summary)
```

## Format `data/crm/case_study_candidates.yaml`

```yaml
candidates:
  - slug: acme-2026
    customer: Acme SAS
    sector: Industrie
    context: PME 80 personnes, app SaaS interne...
    problem: Audit pentest demandé par leur DAF pour conformité ISO 27001.
    solution: Scan Argos full coverage en 3 jours + restitution dirigeants.
    results:
      - 12 findings dont 2 critiques (escalade priv)
      - Patch sous 2 semaines
      - ISO 27001 obtenue 4 mois plus tard
    quote: "Argos a tenu son délai au jour près."
    status: ready
```

## Sortie

`data/marketing/case_studies/<slug>.md` avec sections canoniques
(contexte, problème, solution, résultats, verbatim, next steps).
