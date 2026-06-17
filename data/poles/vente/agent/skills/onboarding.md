---
id: onboarding
role: lifecycle
guardrails: [cadence-J0-J7-J30, idempotent, ton-rassurant, humain-in-the-loop]
---

Drafte les emails d'onboarding dus (J+0 bienvenue + lancer le 1er scan, J+7 lever
les blocages, J+30 récap + appel si NPS bas ou usage faible) à partir des comptes
`customers.yaml`. Idempotent : un step déjà drafté n'est pas re-créé. Ton
rassurant et orienté time-to-value (premier scan). Le fondateur envoie via
`zimbra-ops` après relecture. Aucun envoi automatique (humain-in-the-loop).
