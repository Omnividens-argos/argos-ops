# Utilisation de l'intelligence artificielle chez Argos

> **Source de vérité** pour la page publique `/legal/ai-disclosure` de
> [omnividens.fr](https://omnividens.fr). Conforme au Règlement européen
> sur l'Intelligence Artificielle (AI Act, Règlement UE 2024/1689).
>
> Dernière mise à jour : **2026-05-08**.

---

## 1. En résumé

Argos utilise l'intelligence artificielle à deux niveaux distincts :

1. **Au sein de notre produit** — corrélation des findings de scan en
   chaînes d'attaque exploitables, classification automatique des
   emails entrants, rédaction assistée des rapports
2. **Dans nos opérations internes** — flotte d'agents qui automatise
   notre support, notre prospection et nos publications (ce site
   compris)

Cette page détaille **quels modèles** nous utilisons, **avec quelles
données**, **où elles transitent** et **comment vous pouvez en sortir**
si vous le souhaitez.

---

## 2. Modèles d'IA utilisés

### 2.1 Génération et raisonnement

Nous utilisons **Claude** (modèles Claude Opus / Sonnet de la famille
Claude 4) via l'abonnement Claude Code Pro Max d'Anthropic.

- **Fournisseur :** Anthropic, PBC (États-Unis)
- **Encadrement transferts :** Standard Contractual Clauses 2021 +
  DPA Anthropic
- **Site officiel :** [trust.anthropic.com](https://trust.anthropic.com)

Tous les appels IA partent **depuis l'ordinateur de notre fondateur** ou
de votre propre poste si vous utilisez le scanner Argos en BYOK
(« Bring Your Own Key »). Aucun serveur Argos central ne fait d'appel
LLM en votre nom — c'est un choix d'architecture explicite (cf. notre
[décision technique D-017](https://github.com/Omnividens-argos/argos-ops/blob/main/docs/DECISIONS.md)).

### 2.2 Embeddings (recherche sémantique)

Nous utilisons un modèle **open-source local** pour vectoriser notre
base de connaissance et permettre à nos agents internes (réponses aux
emails support, génération de contenu) de retrouver les informations
pertinentes : `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`.

- **Fournisseur :** modèle open-source publié par la communauté
  scientifique (Microsoft Research + sentence-transformers community)
- **Localisation :** **exécution 100 % locale** sur nos serveurs —
  aucun appel API tiers, aucun transfert international
- **Données :** le contenu de votre email entrant peut être vectorisé
  localement pour identifier les passages pertinents de notre base de
  connaissance ; le vecteur n'est ni stocké ni transmis à un tiers

### 2.3 Modèles spécifiques au scanner Argos (BYOK)

Lorsque vous utilisez **votre clé API personnelle** (BYOK) dans le
scanner Argos pour activer la corrélation IA des findings, vous pouvez
choisir parmi : **Anthropic Claude**, **OpenAI GPT**, **Google Gemini**,
**DeepSeek**.

Dans ce mode :

- Les appels IA partent **de votre poste** ou **de votre instance Argos
  self-hosted**, avec **votre clé**, vers le fournisseur que **vous**
  avez choisi
- Argos n'intermédie ni ne stocke vos prompts
- Vous restez seul responsable du DPA avec votre fournisseur d'IA

---

## 3. Décisions automatisées et profilage

### 3.1 Au sein du produit Argos (scanner)

Le scanner Argos prend des décisions **techniques** automatisées :
exécuter un module, déclarer un finding, calculer un risk score A-F,
construire une chaîne d'attaque. Ces décisions concernent **vos
infrastructures techniques** que vous nous demandez explicitement de
scanner — **pas** des personnes physiques.

- **Pas de profilage RGPD au sens de l'article 22.** Aucune décision
  produisant des effets juridiques ou affectant significativement une
  personne physique n'est prise par notre IA
- **Le risk score** est un indicateur technique calculé selon une
  formule **publique et déterministe** (cf.
  [`argos_features.md` § 4.5](https://github.com/Omnividens-argos/argos-ops/blob/main/data/knowledge_base/argos_features.md))
  que vous pouvez recalculer manuellement
- **Les chaînes d'attaque IA** sont des hypothèses d'exploitation
  fournies à titre indicatif. Vous restez seul juge de leur
  exploitabilité réelle dans votre contexte ; nous ne nous engageons
  ni sur leur exhaustivité ni sur leur certitude

### 3.2 Dans nos opérations internes

Nos agents IA peuvent :

- **Classifier** vos emails entrants (`lead_chaud`, `question_tech`,
  `sav`, `spam`) pour les router au bon traitement
- **Rédiger** un brouillon de réponse à votre email
- **Calculer** un score BANT (Budget, Authority, Need, Timeline) pour
  estimer la qualification commerciale d'un prospect

**Aucune de ces décisions n'a d'effet juridique sur vous.** Tous les
brouillons générés par nos agents sont **systématiquement supervisés**
avant envoi (workflow Tier 0-4 décrit dans notre
[`ESCALATION_RULES.md`](https://github.com/Omnividens-argos/argos-ops/blob/main/docs/ESCALATION_RULES.md)) :
si la confiance est faible, un humain valide le message avant qu'il
parte.

Si vous estimez avoir reçu une réponse manifestement inadaptée à votre
situation, vous pouvez **demander une intervention humaine
systématique** sur l'ensemble de votre fil — voir section 5.

---

## 4. Canal de contact entrant — email exclusivement

Le seul canal d'entrée prospects/visiteurs côté Argos est l'email
([contact@omnividens.fr](mailto:contact@omnividens.fr)). Nous n'avons
**pas de chatbot widget** sur le site (cf. notre
[décision D-019](https://github.com/Omnividens-argos/argos-ops/blob/main/docs/DECISIONS.md) — choix
explicite pour la souveraineté donnée et la cohérence avec D-017).

Lorsque vous nous écrivez :

- **Réponse automatique éventuelle** : un brouillon peut être généré par
  notre agent EmailBot, **systématiquement supervisé par un humain**
  avant envoi quand la confiance est inférieure au seuil (cf. § 3.2).
  Aucun message ne part en mode 100 % auto sans validation humaine
  préalable.
- **Données stockées** : sujet, corps du message, adresse expéditeur,
  pièces jointes éventuelles
- **Durée** : 3 ans après le dernier échange, puis purge automatique
- **Aucun entraînement de modèle** sur vos emails : ni nous, ni
  Anthropic n'utilisent vos messages pour ré-entraîner les modèles.
  Anthropic s'engage par défaut à ne pas utiliser les prompts pour
  le training (cf. [trust.anthropic.com](https://trust.anthropic.com))

---

## 5. Vos droits face à l'IA

Conformément à l'AI Act et au RGPD, vous disposez des droits suivants :

### 5.1 Droit à l'information (article 13 AI Act)

Vous êtes informé que vous interagissez avec un système d'IA dès le
début de chaque interaction (réponses email pouvant être pré-rédigées
par EmailBot puis supervisées humainement avant envoi).

### 5.2 Droit à une intervention humaine

Vous pouvez **demander à tout moment** que votre email ou votre demande
soit traité **par un humain** plutôt que par notre IA. Méthodes :

- **Par email** : ajoutez en début de mail « *Réponse humaine SVP* »,
  le système route automatiquement votre demande hors du pipeline
  IA (Tier 2 — réponse différée < 24 h ouvrées par un humain)
- **Par courrier postal** ou téléphone : la réponse sera de toute façon
  humaine

### 5.3 Droit de contester une décision

Si vous estimez qu'une décision automatisée d'Argos vous porte
préjudice (refus d'inscription, suspension de compte, classification
de votre email comme spam, etc.), contactez
[contact@omnividens.fr](mailto:contact@omnividens.fr) — un humain
réexaminera votre dossier sous 30 jours.

### 5.4 Droit de retrait

Vous pouvez à tout moment :

- Supprimer votre compte Argos (cf. [Politique de confidentialité § 3](privacy.md#3-vos-droits))
- Demander la suppression de tout l'historique IA vous concernant
  (emails classifiés, brouillons générés)
- Refuser que nous utilisions votre dossier comme exemple anonymisé
  pour améliorer nos modèles internes (par défaut, **nous n'utilisons
  jamais vos données pour entraîner ou affiner un modèle d'IA**)

---

## 6. Catégorisation AI Act

Selon le règlement européen sur l'IA (AI Act, en application progressive
2025-2027), nous classifions nos systèmes d'IA comme suit :

| Système | Catégorie AI Act | Justification |
|---|---|---|
| **Scanner Argos — moteur de corrélation IA** | Risque limité (Article 50) | Outil d'aide à la décision technique pour des professionnels de la sécurité, sans impact direct sur des personnes physiques |
| **Classification d'emails entrants / scoring BANT** | Risque limité (Article 50) | Aide à la priorisation interne, supervision humaine systématique avant tout effet externe |
| **Téléphonie IA** (phase 2, non livrée) | Risque limité, à réévaluer | Sera couvert par la même politique le jour où ce module sera mis en service. Pas avant. |

**Aucun de nos systèmes n'entre dans les catégories « Risque inacceptable »
ou « Haut risque »** au sens des articles 5 et 6 de l'AI Act. Nous
n'effectuons pas de notation sociale, pas d'identification biométrique
en temps réel, pas de système d'évaluation des candidats à l'emploi.

---

## 7. Sources et open-source

Argos est partiellement open-source dans son infrastructure d'agents
internes. Vous pouvez consulter :

- **Politique d'IA opérationnelle** :
  [`docs/COMPLIANCE.md`](https://github.com/Omnividens-argos/argos-ops/blob/main/docs/COMPLIANCE.md)
- **Décisions techniques** :
  [`docs/DECISIONS.md`](https://github.com/Omnividens-argos/argos-ops/blob/main/docs/DECISIONS.md)
  (notamment D-011, D-013, D-014, D-017 sur l'IA)
- **Catalogue des modèles utilisés** : ce document, section 2

---

## 8. Contact

Pour toute question sur notre utilisation de l'IA :

- **Email :** [contact@omnividens.fr](mailto:contact@omnividens.fr)
- **Délégué à la protection des données :** voir
  [Politique de confidentialité § 1](privacy.md#1-qui-sommes-nous-)

---

## Notes pour l'intégration frontend (à retirer avant publication)

> Cette section est destinée à l'équipe technique qui intégrera ce
> contenu sur `omnividens.fr` — **à supprimer avant publication
> publique**.
>
> **Placeholders à compléter avant mise en ligne :**
>
> 1. **§ 6** — Re-vérifier la classification AI Act dès qu'un module
>    nouveau est livré (notamment téléphonie IA en phase 2)
> 2. **§ 5.2** — Implémenter côté EmailBot la détection de
>    « *Réponse humaine SVP* » dans le sujet ou les premières lignes
>    → skip auto-reply, escalade ticket Tier 2 humain
>
> **Liens internes à activer côté frontend :**
>
> - `privacy.md` → page Politique de confidentialité
> - Liens GitHub vers les fichiers `docs/` du repo Argos Ops :
>   transparence appréciée par les RSSI techniques, à conserver
>
> **Note 2026-05-12** — chat widget retiré du périmètre par
> [D-019](https://github.com/Omnividens-argos/argos-ops/blob/main/docs/DECISIONS.md).
> Les anciennes sections § 4 (bandeau chat) et § 5.2 (mots-clés
> chat « humain ») ont été réécrites en conséquence.
