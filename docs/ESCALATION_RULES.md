# Argos Ops — Escalation Rules

> Règles précises pour les Tiers 0-4 : qui répond à quoi et quand.

---

## Tiers

| Tier | Acteur | SLA | Volume cible |
|------|--------|-----|--------------|
| 0 | Agent répond directement (pas de juge) | quasi-temps réel | 90 % |
| 1 | Agent-juge IA valide + auto-send | < 2 min | 8 % |
| 2 | File asynchrone, fondateur lit 2× / jour | 24 h | 1.5 % |
| 3 | VA externe (Upwork ~5 €/h) si volume > seuil | 8 h | 0.4 % |
| 4 | Fondateur en synchrone, vrais P0 | < 1 h | 0.1 % |

---

## Critères Tier 0 (auto direct)

L'agent répond sans passer par le juge si **TOUS** ces critères sont remplis :

- Pattern de question reconnu dans la KB avec score similarité ≥ 0.85
- Pas de signal commercial fort (pas d'intention d'achat / négociation tarif)
- Pas de mention de plainte / problème technique critique
- L'agent a un track record de score ≥ 95 sur le pattern

⚠️ **En phase de démarrage, Tier 0 est désactivé** : tout passe par le juge
(Tier 1 minimum) tant que le système n'a pas accumulé 1000+ interactions.

---

## Critères Tier 1 (juge auto-send)

Le juge valide et l'agent envoie automatiquement si :

- `judge.global_score ≥ 80`
- `judge.factual_score ≥ 70` (anti-hallucination)
- `judge.legal_score ≥ 90` (pas de risque conformité)
- Verdict explicite `auto_send`

---

## Critères Tier 2 (file asynchrone fondateur)

L'output passe en file Tier 2 (notif Discord, draft Gmail / brouillon) si :

- `50 ≤ judge.global_score < 80`
- OU `judge.legal_score < 90` (suspicion risque légal)
- OU le sujet contient un signal hot non couvert par la KB
- OU c'est une décision business (tarif / partenariat / témoignage à demander)

Le fondateur traite la file 2× par jour (matin + soir, 5 min chacun).

---

## Critères Tier 3 (VA externe)

Activé seulement si la file Tier 2 dépasse 20 items en attente sur 7 jours
glissants. À ce moment-là on recrute un VA Upwork (~5 €/h, anglophone OK pour
le triage).

Le VA traite les Tier 2 simples (validation de drafts, qualification de leads)
selon un playbook documenté. Les cas vraiment complexes restent sur le fondateur.

---

## Critères Tier 4 (fondateur sync)

Escalade immédiate (notif `@founder` Discord canal `#alerts`) si :

- Plainte client avec menace de churn
- Mention juridique / RGPD / DGCCRF / CNIL
- Anomalie de paiement Stripe (chargeback / dispute)
- Breaker `mrr_drop` tripped (MRR -5 % sur 7j)
- Compromission de sécurité suspectée
- N'importe quel cas où le juge retourne `verdict='killed'` 3 fois consécutives
  sur le même thread

---

## Garde-fous anti-spam d'escalade

Pour éviter de saturer la file Tier 2 :

- Un même lead ne peut générer qu'**une** escalade Tier 2 par jour
- Un thread email avec 3+ aller-retours en 5 min passe direct en Tier 2
  (boucle anti-bot suspectée)
- Si la file Tier 2 dépasse 50 items, breaker `support_low_confidence` trip et
  désactive l'auto-réponse de tous les agents jusqu'à reset manuel
