# PROMPT-6 — Décisions

> Numéro réservé `D-023` ci-dessous. Le founder confirmera le numéro
> définitif lors de la consolidation (peut décaler si une décision
> D-023 a déjà été assignée par un prompt parallèle).

---

## D-023 — Activation OutboundBot P13.B en mode `stage` (fallback du domaine secondaire)

**Date :** 2026-05-23
**Partie :** P13.B (Sprint 3 Sales — P22.H prompt 6)

**Décision :** Livrer le pipeline outbound SMTP réel (`argos_ops/agents/outbound_sender.py`,
slash `/send-outbound-batch`) en **mode `stage`** par défaut, tant que
le domaine secondaire n'est pas acquis et warmé-up. En stage,
l'expéditeur reste `contact@omnividens.fr`, le destinataire est rerouté
vers cette même boîte (audit founder), le sujet est préfixé `[STAGE]`,
le footer RGPD + AI Act + opt-out HMAC est inclus normalement. Le
basculement en mode `live` se fait par flip de 3 variables `.env.local`
(`OUTBOUND_LIVE_MODE=true`, `OUTBOUND_FROM_DOMAIN=<domaine>`,
`OUTBOUND_UNSUBSCRIBE_SECRET=<hex 64>`) — aucune modification de code
requise.

**Pourquoi :**

- Le prompt P22.H acte un pré-requis BLOCANT (domaine secondaire ~10€/an
  acheté + configuré SPF/DKIM/DMARC) AVANT activation P13.B live. Le
  domaine n'est pas encore acquis au 2026-05-23.
- Le prompt prévoit explicitement le fallback : « Si pas dispo, livre
  P13.B en mode stage (envoi vers boîte test) ».
- Le mode `stage` permet de valider en condition réelle tout le
  pipeline (rendering touch, footer RGPD, threading SMTP, idempotence
  du patch `meta.yaml` après envoi) sans aucun risque sur la
  réputation `omnividens.fr` ni le respect Bloctel/BtoB.
- Alternatives écartées :
  - **Bloquer P13.B jusqu'à acquisition du domaine** : laisse 8 bots
    Sales sans le runtime SMTP, casse l'orchestration cross-bot
    (MeetingBooker / DemoFollowupBot dépendent du même chemin SMTP).
  - **Forcer le founder à acheter le domaine maintenant** : décision
    business (budget pub, choix du nom, prestataire DNS) hors
    périmètre technique du sprint.

**Implication technique :**

- `argos_ops/agents/outbound_sender.py:determine_mode()` retourne
  `"stage" | "live" | "disabled"` selon les flags `.env`. Seul l'addr
  destinataire et le préfixe sujet changent entre stage et live.
- `OutboundBot` shadow (`outbound_bot.py`) **reste intact** — il
  continue de scaffold les séquences depuis le CSV inbox. Pas de
  régression des sessions précédentes (P13.A).
- Le partage du breaker `OutboundBot` (P15) entre les deux agents
  garantit qu'un trip arrête à la fois le scaffold ET l'envoi —
  garde-fou délivrabilité unifié.
- Tests : `tests/test_outbound_live.py` couvre les 3 modes
  (stage/live/disabled) + l'idempotence du patch `meta.yaml`.

**Annule :** —

**Action de suivi :**

- [ ] Founder : acheter domaine secondaire + configurer SPF/DKIM/DMARC.
- [ ] Founder : warmup 4 semaines en mode `stage` avant flip `live`
  (cap `OUTBOUND_DAILY_MAX=30` déjà en place).
- [ ] Lors du flip `live`, mettre à jour Annexe D § 3 ligne `OutboundBot`
  de `[~] 🟡` vers `[x] ✅` + ajouter une décision dédiée à l'activation
  effective (audit délivrabilité, conformité Bloctel checklist).

**Réversibilité :**

Totale — il suffit de retirer `OUTBOUND_LIVE_MODE=true` de `.env.local`
pour revenir en stage. Le code et les tests restent inchangés.
