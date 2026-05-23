# P22.H — Sprint 3 Sales — Session 6 (Prompt 6) Summary

**Date :** 2026-05-23
**Branche locale :** `feat/p22h-sales-9-bots` (3 commits, **zéro push**)
**Périmètre :** Annexe D § 3 — 9 bots Sales / Commercial

## Livré

### Pipeline amont (commit 1, `feat(p22h-amont)`)

1. **`argos_ops/sales/`** — module helper partagé (models, enrichment, ical,
   scoring, templates). Tout offline (D-017), zéro dépendance Python ajoutée.
2. **ProspectMiner** ([`argos_ops/agents/prospect_miner.py`](../../argos_ops/agents/prospect_miner.py)) —
   append nouveaux prospects à `data/outbound/inbox/leads.csv` depuis
   RSS publics (annonces légales, Crunchbase news, LinkedIn Jobs auth-free)
   + entrées YAML `manual`. Dedup `(full_name, domain)`, conformité D-016.
3. **LeadEnricher** ([`argos_ops/agents/lead_enricher.py`](../../argos_ops/agents/lead_enricher.py)) —
   porte le skill markdown en agent Python batch. Heuristiques offline
   BANT / persona Marc-Sarah-Thomas / 5 patterns email scorés. Output
   Markdown frontmatter par lead.
4. **IntentSignalsBot** ([`argos_ops/agents/intent_signals.py`](../../argos_ops/agents/intent_signals.py)) —
   capte signaux d'achat publics (breaches CERT-FR, embauches CISO,
   levées Crunchbase). Scoring relevance mot-clé ICP (saas, pme, rgpd,
   ransomware, …). YAML quotidien + Discord top-5.

### Pipeline aval (commit 2, `feat(p22h-aval)`)

5. **MeetingBooker** ([`argos_ops/agents/meeting_booker.py`](../../argos_ops/agents/meeting_booker.py)) —
   drafte email confirmation + invitation iCalendar RFC 5545 par RDV
   pending. Humain-in-the-loop strict.
6. **DemoFollowupBot** ([`argos_ops/agents/demo_followup.py`](../../argos_ops/agents/demo_followup.py)) —
   drafte récap post-démo (pain points, next steps owner/action,
   attachments) depuis YAML saisi à la main.
7. **ProposalBot** ([`argos_ops/agents/proposal_bot.py`](../../argos_ops/agents/proposal_bot.py)) —
   génère devis Markdown + PDF (pandoc si dispo) depuis context.yaml
   par deal. Calcule HT/TVA 20%/TTC + remise.
8. **ContractGenerator** ([`argos_ops/agents/contract_generator.py`](../../argos_ops/agents/contract_generator.py)) —
   génère contrat CGV/MSA depuis le même context une fois le devis
   `proposal_status: sent`. Articles standards RGPD + AI Act.
9. **DealRiskScorer** ([`argos_ops/agents/deal_risk_scorer.py`](../../argos_ops/agents/deal_risk_scorer.py)) —
   score 0-100 chaque deal actif + flag stalled selon seuil par stade
   (7j / 14j / 30j). Discord ORANGE si stalled, GREEN sinon.

### OutboundBot LIVE (P13.B stage mode) — commit 3 (`feat(p22h-outbound-live)`)

10. **OutboundSender** ([`argos_ops/agents/outbound_sender.py`](../../argos_ops/agents/outbound_sender.py)) —
    envoi SMTP réel des touches `drafted` dont `scheduled_date <= today`.
    **Mode stage** par défaut (pas de domaine secondaire) : email rerouté
    vers `contact@omnividens.fr` (soi) avec sujet `[STAGE]`, footer
    RGPD + opt-out HMAC inclus. **Mode live** quand
    `OUTBOUND_LIVE_MODE=true` + `OUTBOUND_FROM_DOMAIN=<domaine>` + 
    `OUTBOUND_UNSUBSCRIBE_SECRET` ⇒ envoi réel vers le lead.
    Préserve `OutboundBot` shadow (`outbound_bot.py`) intact.
    Cf. décision [D-023](PROMPT-6-decisions.md).

## Artefacts secondaires

- 9 slash commands (`.claude/commands/`) : `/run-prospect-mining`,
  `/run-lead-enrich`, `/run-intent-signals`, `/book-meeting`,
  `/draft-demo-followup`, `/draft-proposal`, `/draft-contract`,
  `/run-deal-scoring`, `/send-outbound-batch`.
- 9 scripts CLI (`scripts/run_*.py`) — entrées Task Scheduler.
- **79 tests unitaires** (29 amont + 40 aval + 10 outbound live).
  Tous verts.
- 2 YAML d'exemple (`data/sales/prospects/sources.example.yaml`,
  `data/sales/signals/sources.example.yaml`).
- Annexe D § 3 : 7 bots ✅ + 1 promotion 🟡→✅ (LeadEnricher) + 1 🟡
  (OutboundBot — stage mode livré, live mode attend domaine).
- Compteurs Annexe D mis à jour : 33 active / 3 partial / 43 roadmap.
- `agentCatalog.ts` : 9 lignes Sales basculées en `status: "active"`
  (sauf OutboundBot qui reste `roadmap` avec ref `stage`).

## Non livré (volontaire)

- Connexion API Apollo / Hunter / Clearbit pour LeadEnricher.
  Reportée à P13.B premium si budget. Skill markdown reste en
  fallback humain-in-the-loop.
- Rappels J-1 / H-1 automatiques MeetingBooker (envoi planifié).
  Sprint 3 livre le draft + ICS, la cadence reminder = backlog
  Sprint 4.
- Domaine secondaire outbound (~10€/an) — bloqueur explicite du
  prompt P22.H. Stage mode livré comme fallback documenté en D-023.

## Tests

```bash
uv run pytest tests/test_sales_enrichment.py tests/test_sales_ical.py \
  tests/test_sales_scoring.py tests/test_sales_templates.py \
  tests/test_prospect_miner.py tests/test_lead_enricher.py \
  tests/test_intent_signals.py tests/test_meeting_booker.py \
  tests/test_demo_followup.py tests/test_proposal_bot.py \
  tests/test_contract_generator.py tests/test_deal_risk_scorer.py \
  tests/test_outbound_live.py
# 79 passed
```

## Commits (local only — INTERDICTION DE PUSH)

1. `feat(p22h-amont)` : ProspectMiner + LeadEnricher + IntentSignalsBot + module `sales/`
2. `feat(p22h-aval)` : MeetingBooker + DemoFollowup + Proposal + Contract + DealRisk
3. `feat(p22h-outbound-live)` : OutboundSender stage mode + Annexe D + agentCatalog + ce summary

Tous sur la branche `feat/p22h-sales-9-bots`. Pas de PR. Le founder
consolidera (rebase / merge / push) lors de la session de
consolidation finale du méta-sprint.

## Session 6 OK, prêt pour consolidation.
