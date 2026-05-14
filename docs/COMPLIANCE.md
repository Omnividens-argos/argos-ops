# Argos Ops — Compliance

> RGPD / AI Act / Bloctel / spam laws. **Squelette posé en P2**,
> **rédaction complète livrée en P17 (2026-05-14)** dans
> [`data/legal/privacy.md`](../data/legal/privacy.md) et
> [`data/legal/ai-disclosure.md`](../data/legal/ai-disclosure.md) —
> sources de vérité pour les pages publiques `/legal/privacy` et
> `/legal/ai-disclosure` d'omnividens.fr.

---

## 1. RGPD (collecte et traitement de données)

### 1.1 Données collectées

| Source | Donnée | Finalité | Base légale | Durée |
|--------|--------|----------|-------------|-------|
| Formulaires site | email, nom | suivi commercial | consentement | 3 ans après dernier contact |
| Cold email outbound | email pro, fonction | prospection BtoB | intérêt légitime | 3 ans |
| Stripe | nom, email, CB tokenisée | facturation | exécution contrat | 10 ans (loi FR) |

### 1.2 Droits utilisateurs

- **Accès / rectification / suppression / portabilité** garantis
- Endpoint dédié : `https://omnividens.fr/legal/dsr` (à créer en P17)
- Délai de réponse : 30 jours max
- DPO : externe à engager si > 250 prospects ou > 50 clients (~80 €/mois)

### 1.3 Registre des traitements

À créer en P17 sur le modèle CNIL gratuit. Mis à jour à chaque ajout d'agent
qui collecte de la donnée nouvelle.

### 1.4 Page `/legal/privacy` (P17 ✅ 2026-05-14)

**Rédaction côté Argos Ops** : [`data/legal/privacy.md`](../data/legal/privacy.md)
(260 lignes, 9 sections, source de vérité).

**Intégration frontend SecHunter** : à faire côté repo SecHunter (rend
le markdown ou page statique régénérée). Quelques placeholders à
compléter avant publication publique (cf. § « Notes pour l'intégration
frontend » en fin du markdown) :

- Forme juridique / SIREN / TVA / adresse siège social
- Nom du DPO si externe engagé
- Confirmation des noms réels de cookies émis par le backend
- Confirmation que `analytics.omnividens.fr` (Umami) est actif
- Confirmation `security@omnividens.fr` existe ou pointe vers contact@

---

## 2. Cold email BtoB (P13 OutboundBot)

- **Base légale** : intérêt légitime BtoB (jurisprudence CNIL)
- **Restrictions :**
  - Email pro uniquement (filtre TLD + heuristiques)
  - Pas d'envoi à des particuliers (gmail.com / hotmail.com / outlook.com →
    skip sauf si signalé comme pro par enrichment)
  - Footer obligatoire : nom de l'entreprise + adresse + lien opt-out 1-clic
  - Opt-out 1-clic via `https://omnividens.fr/unsubscribe?token=...`
  - Suppression définitive sous 7 jours après opt-out
  - Pas de relance si opt-out

- **Domaine secondaire** : `try-omnividens.com` ou similaire (~10 €/an) à
  acquérir avant le démarrage P13. Domaine principal `omnividens.fr` JAMAIS
  utilisé pour outbound (préserve la réputation délivrabilité).

---

## 3. AI Act UE

> _Section 3.1 « Chatbot widget » retirée par
> [D-019](DECISIONS.md#d-019--abandon-d%C3%A9finitif-du-chatbot-widget-site-p8-cancelled)
> (2026-05-12) — la P8 chatbot widget est annulée._

### 3.1 Téléphonie IA (phase 2)

- **Annonce obligatoire** en début d'appel : « Vous êtes en relation avec une
  intelligence artificielle »
- À implémenter quand CallerBot sera en phase 2 (reporté hors v1)

### 3.2 Génération de contenu (P9 ContentBot)

- Pas d'AI Act spécifique sur le posting social, mais on garde une trace de
  la génération (champ `interactions.body` + `agent_name='ContentBot'`)
- Aucun deepfake / fausse personne / faux témoignage

---

## 4. Bloctel et démarchage téléphonique

- **Bloctel s'applique au BtoC** uniquement
- Argos cible BtoB (RSSI / DevSecOps / CTO) → hors scope Bloctel
- **MAIS** si CallerBot phase 2 contacte des particuliers (jamais prévu) :
  vérification Bloctel obligatoire avant tout appel

---

## 5. Faux avis / faux témoignages

- **JAMAIS** générer de faux avis ou faux témoignages clients (sanction CNIL +
  DGCCRF, jusqu'à 1.5 M€ d'amende)
- Les avis publics sont sollicités via email post-onboarding J+30 (vrais clients)
- Avis négatifs : on modère uniquement pour insultes / diffamation, jamais pour
  cacher une critique légitime

---

## 6. Logs et observabilité — précautions

- **Aucune clé API en clair dans les logs** (filtre loguru sur patterns
  `sk-`, `AIza`, `gho_`, `WPL_AP1`, `xoxb-`, etc.)
- Logs `agent_runs.body` peuvent contenir des données prospects → rétention
  90 jours puis purge auto
- Logs Discord : éviter de pousser les contenus complets en clair sur les
  canaux d'escalade (résumé + lien vers la DB)

---

## 7. Statut P17 (2026-05-14)

### Done côté Argos Ops

- ✅ Page `/legal/privacy` rédigée → [`data/legal/privacy.md`](../data/legal/privacy.md)
- ✅ Page `/legal/ai-disclosure` rédigée → [`data/legal/ai-disclosure.md`](../data/legal/ai-disclosure.md)
- ✅ Sous-traitants documentés (Anthropic, OVHcloud, Google Workspace,
  Stripe) avec cadre RGPD (DPA + SCC 2021) dans privacy.md § 4
- ✅ Helper Python déterministe
  [`argos_ops/compliance.py`](../argos_ops/compliance.py) — détecte
  les demandes explicites de réponse humaine (AI Act § 5.2). Wired
  dans [`.claude/commands/check-emails.md`](../.claude/commands/check-emails.md)
  en step 2.a.0 (court-circuit AVANT classification). 22 tests.

### À faire hors Argos Ops (côté SecHunter / fondateur)

- ⬜ Intégration frontend des 2 pages legal sur omnividens.fr
- ⬜ Compléter placeholders dans privacy.md (forme juridique, SIREN,
  TVA, adresse siège, DPO externe si nécessaire)
- ⬜ Confirmer que `security@omnividens.fr` existe (ou alias vers
  `contact@omnividens.fr`)
- ⬜ Registre des traitements (modèle CNIL, gratuit) — à créer comme
  document interne séparé, à mettre à jour à chaque nouvel agent qui
  collecte une donnée nouvelle
- ⬜ Contrats type DPA pour clients enterprise (offre Custom ≥ 5 k€/mois,
  cf. privacy.md § 7 — data residency UE stricte)

### Engagement compliance opérationnel

Toute modification de :

- la liste des sous-traitants (privacy.md § 4)
- la classification AI Act (ai-disclosure.md § 6)
- les durées de conservation (privacy.md § 2)
- la liste des phrases déclencheuses « réponse humaine SVP »
  (`argos_ops/compliance.py` + email-classifier SKILL.md)

→ DOIT inclure **« P17 »** dans le commit message + bumper la date en
haut du markdown public. Sert de signal pour le rebuild de la page
publique côté SecHunter et de trace d'audit.
