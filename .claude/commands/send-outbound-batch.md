---
description: Lance OutboundSender (P13.B) — envoie SMTP les touches drafted dont scheduled_date <= today. Mode stage (rerouté → soi) tant que OUTBOUND_FROM_DOMAIN absent.
---

# /send-outbound-batch

Slash command Claude Code invoquée manuellement ou par Task Scheduler (`argos-ops-outbound-sender`, cadence quotidienne 9h Paris) **sur l'ordi du fondateur** (D-017).

## Procédure

1. Pré-requis : séquences scaffold + au moins une touche drafted (via `/run-outbound-bot` puis `/draft-outbound <slug>`).
2. Lance `uv run python scripts/run_outbound_sender.py`.
3. Lis le mode dans l'embed Discord :
   - **`stage`** (défaut) : le mail part vers `contact@omnividens.fr` (soi) avec sujet préfixé `[STAGE]`. Permet de valider le pipeline complet (rendering, footer RGPD, opt-out HMAC, threading) sans toucher au lead ni risquer la réputation du domaine principal.
   - **`live`** : le mail part vers le destinataire réel. Requiert `OUTBOUND_LIVE_MODE=true` ET `OUTBOUND_FROM_DOMAIN=<domaine secondaire>` ET `OUTBOUND_UNSUBSCRIBE_SECRET` configurés.
   - **`disabled`** : `EMAIL_USER` ou `EMAIL_PASSWORD` manquant — configurer Zimbra (D-018) avant tout envoi.
4. **Si `sent > 0`** : `meta.yaml` patché avec `status: sent` + `sent_at`. Pas de double envoi possible.
5. **Si `failures > 0`** : Discord embed orange. Lis les logs loguru pour identifier la cause (SMTP timeout, auth failure, payload trop gros).

## Activation du mode live

1. Acheter un domaine secondaire (~10€/an, ex : `try-omnividens.com`). Le prompt P22.H exige ce pré-requis BLOCANT pour passer en live.
2. Configurer SPF + DKIM + DMARC sur le domaine secondaire (warmup 4 semaines, pas plus de 30 emails/jour la première semaine).
3. Positionner dans `.env.local` :
   ```dotenv
   OUTBOUND_LIVE_MODE=true
   OUTBOUND_FROM_DOMAIN=try-omnividens.com
   OUTBOUND_UNSUBSCRIBE_SECRET=<32 octets hex>
   ```
4. Re-lancer `/send-outbound-batch` : l'embed Discord doit passer en `mode: live`.

## Garde-fous

- Daily cap `OUTBOUND_DAILY_MAX` (défaut 30) — protection délivrabilité.
- Breaker `OutboundBot` (P15) — partagé avec OutboundBot shadow. Reset via `/reset-breaker outbound_volume_exceeded` après audit.
- Footer RGPD + AI Act + opt-out HMAC 1-clic ajouté automatiquement à chaque envoi (cf. `argos_ops.outbound.templates.build_footer`).
- Ne touche jamais aux touches `scaffold` (sans body). Drafter via `/draft-outbound <slug>` d'abord.
