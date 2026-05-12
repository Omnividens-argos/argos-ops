# Politique de confidentialité

> **Source de vérité** pour la page publique `/legal/privacy` de
> [omnividens.fr](https://omnividens.fr). Contenu RGPD-compliant rédigé en
> P17-PREP. À intégrer dans le frontend SecHunter (composant React qui
> rend ce markdown ou page statique régénérée).
>
> Dernière mise à jour : **2026-05-08** (à actualiser à chaque modification
> matérielle ; le footer doit afficher cette date au visiteur).

---

## 1. Qui sommes-nous ?

**Omnividens** édite **Argos**, un scanner de sécurité applicative (DAST,
SAST, cloud, network). Cette politique décrit comment nous traitons vos
données personnelles lorsque vous visitez [omnividens.fr](https://omnividens.fr),
créez un compte, utilisez le scanner ou nous contactez.

**Responsable du traitement :**

- **Raison sociale :** Omnividens [À COMPLÉTER : forme juridique — SAS, EURL, etc.]
- **SIREN :** [À COMPLÉTER]
- **Numéro de TVA intracommunautaire :** [À COMPLÉTER — FR XX XXXXXXXXX]
- **Siège social :** [À COMPLÉTER : adresse postale complète]
- **Email de contact :** [contact@omnividens.fr](mailto:contact@omnividens.fr)
- **Délégué à la protection des données (DPO) :** [À COMPLÉTER : externe à
  engager si > 250 prospects ou > 50 clients, cf. section 8 ci-dessous.
  Tant que non engagé, le contact RGPD est `contact@omnividens.fr`]

---

## 2. Quelles données collectons-nous, et pourquoi ?

Nous collectons uniquement les données nécessaires à la fourniture du
service ou au respect d'obligations légales. Le tableau ci-dessous est
**exhaustif** au 2026-05-08 — toute nouvelle source de collecte fera
l'objet d'une mise à jour de ce document.

| Source | Données collectées | Finalité | Base légale | Durée de conservation |
|---|---|---|---|---|
| **Création de compte / formulaires site** | Email, prénom, nom, mot de passe (haché bcrypt) | Identification, authentification, suivi commercial | Exécution d'un contrat (compte gratuit ou payant) + consentement | 3 ans après le dernier contact actif |
| **Cibles scannées** (URL, IP, domaines, repos code) | Que vous nous fournissez vous-même | Exécution du scan et restitution du rapport | Exécution d'un contrat | Selon votre tier — Free 30 j, Pro 90 j, Team 1 an, Pro Max illimité (cf. notre [grille pricing](/pricing)) |
| **Findings de scan** (vulnérabilités détectées sur vos cibles) | Métadonnées techniques (URL endpoint, sévérité CVSS, payload, oracle) | Restitution rapport, historique, comparaison run-à-run (Watch) | Exécution d'un contrat | Idem cibles scannées |
| **Cold email outbound** (prospection BtoB) | Email professionnel, fonction, raison sociale | Prospection BtoB ciblée | Intérêt légitime BtoB (jurisprudence CNIL ; opt-out 1-clic systématique) | 3 ans, ou jusqu'à opt-out (suppression sous 7 jours) |
| **Stripe** (paiements abonnements) | Nom, email, partie tokenisée carte bancaire (Stripe ne nous expose **jamais** le numéro complet) | Facturation, prélèvements récurrents, gestion abonnements | Exécution d'un contrat + obligation légale (article L.123-22 Code de commerce) | 10 ans (durée légale comptable FR) |
| **Emails entrants** (`contact@omnividens.fr`) | Adresse expéditeur, sujet, corps du message, pièces jointes | Réponse au message, qualification commerciale, support technique | Exécution de mesures pré-contractuelles (vous nous contactez) + intérêt légitime (suivi commercial) | 3 ans après le dernier échange, puis purge automatique |
| **Logs serveurs / agents IA** | Adresses IP appelantes, requêtes HTTP, identifiants de scan | Sécurité, débogage, observabilité | Intérêt légitime (sécurité du service) | 90 jours, puis purge automatique |

**Aucun cookie de tracking publicitaire n'est déposé** sans votre
consentement explicite. Notre site utilise uniquement des cookies
strictement nécessaires (session, préférences) et un cookie d'analytics
self-hosted (Umami, données agrégées anonymes — cf. section 6).

---

## 3. Vos droits

Vous disposez des droits suivants sur vos données, garantis par les
articles 15 à 22 du Règlement Général sur la Protection des Données
(RGPD) :

- **Droit d'accès** — savoir quelles données nous détenons sur vous
- **Droit de rectification** — corriger des données inexactes
- **Droit à l'effacement** (« droit à l'oubli ») — demander la suppression
  de vos données
- **Droit à la limitation du traitement** — geler temporairement le
  traitement le temps de vérifier une contestation
- **Droit d'opposition** — vous opposer au traitement (notamment cold
  email outbound : opt-out 1-clic dans chaque mail)
- **Droit à la portabilité** — récupérer vos données dans un format
  structuré (JSON / CSV) pour les transmettre à un autre service
- **Droit de réclamation** auprès de la CNIL (Commission Nationale de
  l'Informatique et des Libertés) si vous estimez que vos droits ne
  sont pas respectés : [www.cnil.fr](https://www.cnil.fr)

### Comment exercer vos droits

Trois moyens, au choix :

1. **Depuis votre compte Argos** — section *Settings → Vie privée*
   (suppression de scan unitaire, export JSON, suppression complète du
   compte). Effet immédiat.
2. **Par email** à [contact@omnividens.fr](mailto:contact@omnividens.fr)
   en précisant la nature de votre demande. Réponse sous **30 jours
   maximum** (article 12 du RGPD).
3. **Par courrier postal** à l'adresse du siège social ci-dessus.

Pour la suppression complète de votre compte, vous pouvez aussi appeler
directement l'endpoint
[`DELETE /api/user/account`](https://omnividens.fr/docs/api#delete-account)
authentifié. Soft delete + anonymisation immédiate ; les scans restent
en base pour intégrité technique mais ne sont plus liables à votre
identité. Sur demande écrite, suppression définitive (« hard delete »)
sous 30 jours.

---

## 4. Sous-traitants et destinataires des données

Vos données peuvent être traitées par les sous-traitants suivants, tous
**localisés en Union européenne ou couverts par un cadre de transfert
adéquat** (Standard Contractual Clauses, Decision d'adéquation) :

| Sous-traitant | Service | Localisation | Cadre RGPD |
|---|---|---|---|
| **Anthropic** | Claude (LLM utilisé pour la corrélation IA des findings, via abonnement Claude Code Pro Max — cf. [D-017](https://github.com/Omnividens-argos/argos-ops/blob/main/docs/DECISIONS.md)) | États-Unis | Standard Contractual Clauses + DPA Anthropic (cf. [trust.anthropic.com](https://trust.anthropic.com)) |
| **Google Workspace** | Gmail (boîte `contact@omnividens.fr`) | UE | DPA Google Workspace |
| **OVHcloud** | Hébergement serveur (France/Allemagne/Pays-Bas) + email pro Zimbra | UE | DPA OVH (souveraineté française) |
| **Stripe** | Traitement des paiements et facturation | UE (entité Stripe Payments Europe Ltd, Irlande) | DPA Stripe |

**Aucun appel API LLM tiers** (Gemini, OpenAI direct, Voyage…) n'est
effectué par Argos Ops dans le cadre du fonctionnement interne — toute
la corrélation IA passe par Claude Code Pro Max et un modèle
d'embedding open-source local (cf. notre [décision D-017](https://github.com/Omnividens-argos/argos-ops/blob/main/docs/DECISIONS.md)).
Cela nous permet de garantir que **vos prompts et findings ne transitent
jamais chez un fournisseur d'IA tiers** pendant le traitement.

> **Pour les clients du scanner Argos avec BYOK** (« Bring Your Own Key »
> Pro+) : si vous fournissez votre propre clé API IA dans Settings, les
> appels IA pendant **vos** scans utilisent **votre** clé, pas la nôtre.
> Cela ajoute votre fournisseur d'IA choisi à la liste de vos
> sous-traitants — vous restez responsable du DPA avec ce fournisseur.

---

## 5. Sécurité

Nous appliquons les mesures suivantes pour protéger vos données :

- **Chiffrement en transit** — TLS 1.2+ obligatoire sur tous les
  endpoints publics
- **Chiffrement au repos** — clés API utilisateur (BYOK) chiffrées AES-256-GCM
  avec une master key dédiée jamais exposée
- **Hachage des mots de passe** — bcrypt avec coût ≥ 12
- **Logs filtrés** — aucun secret d'API ni token webhook n'est écrit en
  clair dans nos logs (filtre programmatique sur patterns connus)
- **Sauvegardes** — `pg_dump` quotidien, conservation 30 jours
- **Accès limité** — seul le personnel autorisé peut consulter les
  données, avec authentification multi-facteur sur les outils
  d'administration

En cas de violation de données susceptible d'engendrer un risque pour
vos droits et libertés, nous vous notifierons dans un délai de 72 heures
après en avoir pris connaissance, conformément à l'article 33 du RGPD.

---

## 6. Cookies et traceurs

Notre site utilise un nombre minimal de cookies, regroupés en deux
catégories :

### 6.1 Cookies strictement nécessaires (sans consentement requis)

| Nom | Finalité | Durée |
|---|---|---|
| `argos_session` | Authentification de votre session connectée | Session (supprimé à la fermeture du navigateur) |
| `argos_csrf` | Protection contre les attaques CSRF | Session |
| `argos_cookie_choice` | Mémorisation de votre choix sur les cookies analytics | 6 mois |

### 6.2 Cookies d'analyse (consentement explicite requis — bandeau)

| Nom | Service | Finalité | Données collectées | Durée |
|---|---|---|---|---|
| `_pk_id` / `_pk_ses` | **Umami** (self-hosted, sans aucun tiers) | Statistiques agrégées de fréquentation (pages vues, sources de trafic) sans aucune donnée personnelle identifiante | Anonymisées (IP tronquée, hash daily de l'identifiant visiteur) | 13 mois (norme CNIL) |

**Pas de Google Analytics, pas de Facebook Pixel, pas de LinkedIn
Insight Tag, pas de Hotjar.** Notre analytics est self-hosted en
Europe (instance Umami sous le sous-domaine `analytics.omnividens.fr`)
et ne partage aucune donnée avec des tiers.

Vous pouvez modifier votre choix de cookies à tout moment via le lien
*Préférences cookies* en pied de page.

---

## 7. Transferts hors UE

Comme indiqué en section 4, certains de nos sous-traitants (notamment
Anthropic pour le service Claude) sont localisés aux États-Unis. Ces
transferts sont encadrés par les **Clauses Contractuelles Types** (SCC)
de la Commission européenne 2021, complétées par des mesures
techniques (chiffrement en transit, ségrégation des données).

Pour les clients qui exigent contractuellement une garantie **data
residency UE stricte** (interdiction totale de tout transfert hors UE),
nous proposons une offre **Custom contact** (≥ 5 000 €/mois) qui inclut
cette garantie en clause MSA. Contactez-nous à
[contact@omnividens.fr](mailto:contact@omnividens.fr) pour en discuter.

---

## 8. Modifications de cette politique

Nous pouvons mettre à jour cette politique pour refléter des évolutions
techniques, légales ou organisationnelles. La date en haut de la page
indique la dernière révision.

**Modifications matérielles** (nouveau sous-traitant, nouvelle finalité
de traitement, allongement d'une durée de conservation, etc.) :

- Notification par email aux titulaires de comptes Argos actifs
- Bandeau persistant sur le site pendant 30 jours
- Possibilité de refuser et résilier sans pénalité

**Modifications mineures** (correction de coquille, ajout d'une
précision sans changement de portée) : pas de notification, mais date
de révision en haut de page mise à jour.

---

## 9. Contact

Pour toute question relative à cette politique ou à vos données :

- **Email :** [contact@omnividens.fr](mailto:contact@omnividens.fr)
- **Postal :** [À COMPLÉTER : adresse du siège social]
- **Délai de réponse :** 30 jours maximum

Pour exercer un droit RGPD : voir section 3.

Pour signaler un incident de sécurité (vulnérabilité, suspicion de
compromission, fuite de données) : `security@omnividens.fr`. Nous
nous engageons à accuser réception sous 24 heures et à traiter
toute remontée responsable de sécurité (Responsible Disclosure).

---

## Notes pour l'intégration frontend (à retirer avant publication)

> Cette section est destinée à l'équipe technique qui intégrera ce
> contenu sur `omnividens.fr` — **à supprimer avant publication
> publique**.
>
> **Placeholders à compléter avant mise en ligne :**
>
> 1. **Section 1** — Forme juridique, SIREN, TVA intra, adresse siège social
> 2. **Section 1** — DPO (nom + email si externe engagé, sinon mention
>    « le contact RGPD est `contact@omnividens.fr` »)
> 3. **Section 6.1** — Vérifier les noms de cookies réels émis par le
>    backend (`argos_session` etc. sont des suppositions cohérentes
>    mais à confirmer avec le code FastAPI)
> 4. **Section 6.2** — Confirmer que l'instance Umami sera bien sur
>    `analytics.omnividens.fr` (cf. INFRA-02)
> 5. **Section 9** — Confirmer que `security@omnividens.fr` existe
>    bien comme alias / boîte (sinon le créer ou pointer vers
>    `contact@omnividens.fr`)
>
> **Liens internes à activer côté frontend :**
>
> - `/pricing` → page tarifs (existante)
> - `/legal/ai-disclosure` → page AI disclosure (livrée en parallèle,
>   cf. [`data/legal/ai-disclosure.md`](ai-disclosure.md))
> - `/docs/api#delete-account` → ancre dans la doc API (à créer en P17
>   complet ou plus tard)
>
> **Layout suggéré :** rendu Markdown standard (Tailwind prose ou
> équivalent), table des matières en sticky-sidebar à droite, lien
> *Préférences cookies* dans le footer global du site.
