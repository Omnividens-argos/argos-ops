# Argos Ops — Agents Playbook

> Détail des 12 agents : objectif, déclencheur, scopes, garde-fous, KPIs.
> Ce fichier sera **enrichi à mesure** que chaque agent est implémenté
> (P4 → P14). Pour l'instant, squelette de référence.

---

## Tableau d'ensemble

| Agent | Partie | Sprint | Trigger | Tier 0 cible | Status |
|-------|--------|--------|---------|--------------|--------|
| Digest | P4 | 0 | cron `0 8 * * *` | 100 % auto | ⬜ |
| EmailBot | P5 | 1 | cron `*/15 * * * *` | 90 % | ⬜ |
| SupportBot | P6 | 1 | déclenché par EmailBot/ChatBot | 85 % | ⬜ |
| FinanceBot | P7 | 1 | cron `0 6 * * *` | 100 % auto | ⬜ |
| ChatBot | P8 | 1 | webhook (visiteurs site) | 90 % | ⬜ |
| ContentBot | P9 | 2 | cron 2-5×/jour | 80 % | ⬜ |
| SEOBot | P10 | 2 | cron `0 6 * * 1` (lundi) | 100 % auto | ⬜ |
| AdBot | P12 | 3 | cron `0 */4 * * 9-18` | 70 % (shadow mode 100%) | ⬜ |
| OutboundBot | P13 | 3 | cron `0 9 * * 1-5` | 80 % | ⬜ |
| ClaudeJudge | P14 | 4 | inline (skill) | 100 % | ⬜ |
| Breakers | P15 | 4 | hooks PreToolUse | 100 % | ⬜ |
| AdminPanel | P16 | 1→4 | UI react | n/a (humain) | ⬜ |

Status : ⬜ pending · 🔄 in progress · ✅ done

---

## Pattern commun

Chaque agent suit le même pattern :

1. **Lecture** `agent_config` (table SQL) — peut désactiver / scaler / pauser
2. **Vérification** `breakers` (table SQL) — un breaker tripped skip l'agent
3. **Exécution** du job métier
4. **Soumission** des outputs sortants à `ClaudeJudge` (P14)
5. **Logging** dans `agent_runs` (table SQL)
6. **Hooks** Discord pour événements humains (escalades, breakers tripped)

Le wrapper Python `argos_ops.agent_runtime.run_if_enabled()` encapsule les
étapes 1, 2 et 5 — chaque slash command appelle ce wrapper en premier.

---

## Détail agent par agent

> _Sections à remplir au fur et à mesure de l'implémentation._

### Digest (P4)
**Objectif :** envoyer un récap matin sur Discord (KPIs J-1 + escalades en
attente + breakers actifs).
**Implémentation :** voir P4.

### EmailBot (P5)
**Objectif :** lire `contact@omnividens.fr`, classifier, drafter, répondre auto
si Tier 0/1, sinon Tier 2.
**Implémentation :** voir P5.

### SupportBot (P6)
**Objectif :** RAG sur la KB pour répondre aux questions techniques entrantes.
**Implémentation :** voir P6.

### FinanceBot (P7)
**Objectif :** facturation Stripe, relances impayés, MRR.
**Implémentation :** voir P7.

### ChatBot (P8)
**Objectif :** widget chat live sur `omnividens.fr`.
**Implémentation :** voir P8.

### ContentBot (P9)
**Objectif :** 2-5 posts/jour LinkedIn / Mastodon / Reddit (D-004 : remplacement X).
**Implémentation :** voir P9.

### SEOBot (P10)
**Objectif :** briefs blog hebdomadaires basés sur SERP gaps.
**Implémentation :** voir P10.

### AdBot (P12)
**Objectif :** pilotage Google / Meta / LinkedIn Ads. Shadow mode tant que
budget = 0.
**Implémentation :** voir P12.

### OutboundBot (P13)
**Objectif :** cold email 30-50/jour vers ICP, séquence 5-touch.
**Implémentation :** voir P13.

### ClaudeJudge (P14)
**Objectif :** LLM secondaire qui audite chaque output avant envoi.
**Implémentation :** voir P14.
