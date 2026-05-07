# Argos Ops — Progress

> Suivi de l'avancement des 19 parties du plan.
> Source : [`docs/ARGOS_OPS_PLAN.md`](../../the%20good%20guy/docs/ARGOS_OPS_PLAN.md) (dans le repo SecHunter).
> À mettre à jour à chaque clôture de partie (règle « Clôture de partie » du master prompt).

---

## Résumé d'avancement

- **Sessions terminées :** 2 / 19 (P0 + P1)
- **Phase en cours :** Sprint 0 (Bootstrap + setup)
- **Dernière partie done :** P1 — Préparation technique
- **Prochaine partie :** P2 — Bootstrap du dossier `argos-ops` (en cours)

---

## Parties

| # | Titre | Sprint | Statut | Date |
|---|-------|--------|--------|------|
| 0 | Vision et décisions préalables | — | ✅ done | 2026-05-07 |
| 1 | Préparation technique et choix d'hébergement | — | ✅ done (partiel) | 2026-05-07 |
| 2 | Bootstrap du dossier `argos-ops` | Sprint 0 | 🔄 in progress | — |
| 3 | Schéma CRM + Knowledge Base | Sprint 0 | ⬜ pending | — |
| 4 | `/morning-digest` (premier slash command) | Sprint 0 | ⬜ pending | — |
| 5 | EmailBot inbound | Sprint 1 | ⬜ pending | — |
| 6 | SupportBot Tier 1 (RAG sur KB) | Sprint 1 | ⬜ pending | — |
| 7 | FinanceBot (Stripe + relances) | Sprint 1 | ⬜ pending | — |
| 8 | Chatbot widget site (Gemini free) | Sprint 1 | ⬜ pending | — |
| 9 | ContentBot multi-canal | Sprint 2 | ⬜ pending | — |
| 10 | SEOBot stratégie + briefs | Sprint 2 | ⬜ pending | — |
| 11 | Connecteurs sociaux (LinkedIn / Mastodon / Reddit) | Sprint 2 | ⬜ pending | — |
| 12 | AdBot (pilotage Google/Meta/LinkedIn Ads) | Sprint 3 | ⬜ pending | — |
| 13 | OutboundBot (cold email volume modéré) | Sprint 3 | ⬜ pending | — |
| 14 | Agent-juge Tier 1 (supervision IA) | Sprint 4 | ⬜ pending | — |
| 15 | Circuit breakers et kill switches | Sprint 4 | ⬜ pending | — |
| 16 | Admin Control Panel (4 phases) | Sprints 1→4 | ⬜ pending | — |
| 17 | Conformité RGPD / AI Act / Bloctel | Continu | ⬜ pending | — |
| 18 | Inventaire des skills | Continu | ⬜ pending | — |
| 19 | Maintenance et observabilité | Continu | ⬜ pending | — |

Légende : ✅ done · 🔄 in progress · ⚠️ partial · 🚫 blocked · ⬜ pending

---

## Détail par partie

### P0 — Vision et décisions préalables ✅
**Done le 2026-05-07.** 5 décisions structurantes prises (D-001 à D-005, voir
`DECISIONS.md`). Pas de code livré. Décisions 4 (budget pub) et 5 (email
`contact@omnividens.fr`) repoussées à leur partie respective comme prévu.

### P1 — Préparation technique ✅ (partielle)
**Done le 2026-05-07.** 7 sous-tâches :
- ✅ P1.A Google AI Studio : clé Gemini validée (49 modèles)
- ✅ P1.B Discord : serveur + 4 webhooks + user ID
- ⏸️ P1.C Reddit : skippé (compte trop neuf, todo `P11-PREP`)
- ⏸️ P1.D X : skippé (free tier supprimé, remplacé par Mastodon — D-004)
- ✅ P1.E LinkedIn : 2 apps + Community Management API soumis (en attente 3-7j)
- ⏸️ P1.F Plausible : skippé (Umami à installer en INFRA-02)
- ✅ P1.G Validation finale

**Secrets stockés** dans `argos-ops/.env.local` (gitignored).

---

## Sessions transverses (non numérotées)

| ID | Titre | Statut | Note |
|----|-------|--------|------|
| INFRA-01 | (réservé pour future install lourde si besoin) | — | — |
| INFRA-02 | Install Umami self-host | ⬜ pending | Avant P10 ou P12 |
| P11-PREP-A | Recréer Reddit App (compte vieilli) | ⬜ pending | Avant P11 |
| P11-PREP-B | Créer compte Mastodon infosec.exchange + token | ⬜ pending | Avant P11 |
| P17-PREP | Créer vraie page `/legal/privacy` sur omnividens.fr | ⬜ pending | Avant P5 |
| P1.E-FOLLOWUP | Vérifier approbation Community Management API LinkedIn | ⬜ pending | 3-7j après 2026-05-07 |

---

## Métriques globales (à remplir à mesure)

- **Skills `argos-ops` créés :** 0 / 14 prévus (voir P18)
- **Slash commands installés :** 0
- **Agents en production :** 0 / 12
- **Coût mensuel cumulé Argos Ops :** 0 € (cible : ≤ 1 €/mois en croisière)
