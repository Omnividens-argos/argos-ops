# Argos Ops — Compliance

> RGPD / AI Act / Bloctel / spam laws. Détail à compléter en P17.
> Squelette posé en P2 pour servir de référence dès les premiers agents.

---

## 1. RGPD (collecte et traitement de données)

### 1.1 Données collectées

| Source | Donnée | Finalité | Base légale | Durée |
|--------|--------|----------|-------------|-------|
| Formulaires site | email, nom | suivi commercial | consentement | 3 ans après dernier contact |
| Cold email outbound | email pro, fonction | prospection BtoB | intérêt légitime | 3 ans |
| Stripe | nom, email, CB tokenisée | facturation | exécution contrat | 10 ans (loi FR) |
| Chat widget | messages, IP, user-agent | amélioration service | consentement (bandeau) | 1 an |

### 1.2 Droits utilisateurs

- **Accès / rectification / suppression / portabilité** garantis
- Endpoint dédié : `https://omnividens.fr/legal/dsr` (à créer en P17)
- Délai de réponse : 30 jours max
- DPO : externe à engager si > 250 prospects ou > 50 clients (~80 €/mois)

### 1.3 Registre des traitements

À créer en P17 sur le modèle CNIL gratuit. Mis à jour à chaque ajout d'agent
qui collecte de la donnée nouvelle.

### 1.4 Page `/legal/privacy`

> ⚠️ **TODO P17-PREP** : créer une vraie page React `/legal/privacy` sur
> `omnividens.fr` (actuellement le serveur retourne 200 mais c'est la homepage
> déguisée). Cette URL a été déclarée à LinkedIn comme privacy policy de
> l'app dev — doit avoir un vrai contenu RGPD avant la mise en service de
> EmailBot (P5).

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

### 3.1 Chatbot widget (P8)

- **Bandeau au démarrage** : « Vous discutez avec une intelligence artificielle.
  Vos messages sont stockés pour amélioration du service. »
- Lien vers `/legal/ai-disclosure` (à créer en P17)
- Respect du consentement cookies (pas de tracking analytics sans consent)

### 3.2 Téléphonie IA (phase 2)

- **Annonce obligatoire** en début d'appel : « Vous êtes en relation avec une
  intelligence artificielle »
- À implémenter quand CallerBot sera en phase 2 (reporté hors v1)

### 3.3 Génération de contenu (P9 ContentBot)

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

## 7. À compléter en P17

- Registre des traitements (modèle CNIL)
- Page `/legal/privacy` complète
- Page `/legal/ai-disclosure`
- Contrats type DPA pour clients
- Sous-traitants : Anthropic (Claude — abonnement Pro Max via Claude Code,
  D-017), Google (Gmail uniquement — pas Gemini, cf. D-017), Stripe — à
  documenter avec leurs DPA respectifs
