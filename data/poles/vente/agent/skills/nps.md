---
id: nps
role: lifecycle
guardrails: [post-onboarding-J14, post-renew-J21, une-question-simple, humain-in-the-loop]
---

Drafte les demandes NPS dues : post-onboarding (J+14 après `onboarding_done_at`)
et post-renew (J+21 après `last_renew_at`), uniquement si le dernier NPS est
antérieur au déclencheur. Une question simple 0-10 + champ commentaire libre, zéro
incentive (biais). Le fondateur envoie via `zimbra-ops` ; le score collecté
alimente ensuite `health_score`, `churn_predictor`, `review` et `testimonial`.
