# `data/outbound/`

Pipeline OutboundBot (P13, shadow mode tant que `OUTBOUND_LIVE_MODE=false`).

## Arborescence

```
data/outbound/
├── inbox/              # CSV de leads à traiter (manual feed)
│   └── leads.csv       # format : full_name,domain,title_hint,linkedin_url
├── enriched/           # output skill `lead-enricher`
│   └── <slug>.md       # fiche prospect (email guesses, BANT, signaux ICP)
└── sequences/          # output OutboundBot + /draft-outbound
    └── <slug>/
        ├── meta.yaml   # SequenceState (status, opt-out token, cadence)
        ├── touch_1.md  # Discovery (D+0) — opener perso + 1 question
        ├── touch_2.md  # Value (D+3) — drop blog / mini-démo
        ├── touch_3.md  # Case (D+7) — étude de cas chiffrée
        ├── touch_4.md  # Proof (D+14) — preuve sociale
        └── touch_5.md  # Breakup (D+30) — break-up email court
```

## Workflow (P13.A shadow)

1. Fondateur exporte une liste depuis LinkedIn Search (ou ailleurs) →
   place dans `inbox/leads.csv`
2. Cron / slash `/run-outbound-bot` lance `OutboundBot` :
   - Lit `leads.csv`
   - Pour chaque lead non encore scaffold, crée `sequences/<slug>/` avec
     5 touches placeholders + cadence D+0/D+3/D+7/D+14/D+30 + opt-out
     token HMAC pré-calculé
   - Notif Discord avec la liste des slugs créés
3. Pour chaque slug, le fondateur lance `/draft-outbound <slug>` (humain-in-the-loop) :
   - Invoque `lead-enricher` → produit `enriched/<slug>.md`
   - Invoque `outbound-personalizer` → ajoute `personalizer.line_1`
   - Rédige le body de chaque touche (manuel ou futur skill `outbound-drafter`)
   - Audit `claude-judge` sur chaque touche avant écriture
4. **Aucun envoi** tant que `OUTBOUND_LIVE_MODE=true` ET domaine secondaire
   acheté ET secret HMAC configuré (P13.B live mode).

## Format CSV `inbox/leads.csv`

Header obligatoire, colonnes :

| Colonne | Obligatoire | Exemple |
|---------|-------------|---------|
| `full_name` | ✅ | `Marc Dupont` |
| `domain` | ✅ | `acme.fr` |
| `title_hint` | optionnel | `RSSI` |
| `linkedin_url` | optionnel | `https://linkedin.com/in/marc-dupont` |

Les lignes vides ou commençant par `#` sont ignorées (commentaires).

## Conformité (P17)

- **Intérêt légitime BtoB** (RGPD art. 6.1.f) — emails pro uniquement,
  jamais d'emails perso (`@gmail.com`, `@yahoo.fr`, etc. → disqualifiés
  par `lead-enricher`)
- **Opt-out 1-clic** dans le footer de chaque touche via URL HMAC-signée
  `https://omnividens.fr/unsubscribe?email=...&t=...`
- **Rétention 12 mois max** — purge `data/outbound/sequences/` au-delà
  (mécanisme à câbler quand on aura un volume réel — P13.B+)
- **AI Act art. 50** — disclosure IA dans le footer
  (`EMAIL_SIGNATURE_AI_DISCLOSURE`)
- **Bloctel non applicable** — Bloctel concerne la prospection téléphonique
  BtoC. L'email outbound BtoB est régi par RGPD intérêt légitime.

## Sécurité — `OUTBOUND_UNSUBSCRIBE_SECRET`

Génère le secret avec :

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Place-le dans `.env.local`. **Ne jamais le changer une fois en prod** —
rotation = revocation globale de tous les liens d'opt-out déjà envoyés.

## Cap journalier

`OUTBOUND_DAILY_MAX` (défaut 30) protège contre un export CSV massif
accidentel. Si > 30 nouveaux leads dans `inbox/leads.csv`, le breaker
`outbound_volume_exceeded` se déclenche et bloque l'agent jusqu'à
`/reset-breaker outbound_volume_exceeded`.

Cadence prévue (warmup 4 semaines avant croisière) :

| Phase | Daily max conseillé |
|-------|---------------------|
| Warmup S1 | 5 |
| Warmup S2 | 10 |
| Warmup S3 | 20 |
| Warmup S4 | 30 |
| Croisière | 30-50 |
