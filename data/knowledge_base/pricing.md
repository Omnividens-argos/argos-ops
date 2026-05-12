# Pricing — Argos / Omnividens

> Référentiel pricing canonique. **Source de vérité** pour la page Pricing
> publique, SupportBot, OutboundBot, FinanceBot et tout
> document mentionnant un prix.
>
> Source : interview fondateur en P3-M2 (2026-05-07). Si un autre fichier
> KB cite un prix différent, **ce fichier prime** — créer une PR pour aligner.

---

## 1. TL;DR — la grille

**4 tiers publics + 1 carte « Custom contact » discrète.** Toutes les boîtes
sont en EUR HT. Engagement annuel = **-20 %**, payé en une fois à la
souscription.

| Tier | Mensuel HT | Annuel HT (-20 %) | Cible ICP | Auto |
|---|---|---|---|---|
| **Free** | 0 € | — | Goûter, Thomas freelance occasionnel | self-serve |
| **Pro** | 39 € | 31 €/mois (372 €/an) | Thomas freelance régulier, side-project Marc | self-serve |
| **Team** | 129 € | 103 €/mois (1 240 €/an) | **Marc CTO scaleup — cœur de cible** | self-serve |
| **Pro Max** | 249 € | 199 €/mois (2 388 €/an) | Sarah Head of Sec mid-market, prep SOC2 | self-serve |
| Custom contact | sur devis ≥ 5 000 €/mois | sur devis | SLA contractuel / MSA / data residency garantie | demo + contrat |

**Pas d'« Enterprise » public au launch.** La carte « Custom contact » est
discrète sur la page Pricing → devis custom à partir de 5 000 €/mois. À
ouvrir sérieusement quand on aura SOC2 + un account manager dédié (pas
avant 6-12 mois).

### Politique grandfather (déjà codée)

Les abonnés payants antérieurs à la refonte (anciens Pro 30 € et anciens
Pro Max 70 €) **gardent leur tarif** via leur `price_id` Stripe legacy
reconnu par le webhook. **Pas de migration forcée**. Si un de ces clients
fait un changement de plan volontaire, il bascule sur la nouvelle grille.

---

## 2. Détail des fonctionnalités par tier

| | Free | Pro (39 €) | Team (129 €) | Pro Max (249 €) |
|---|---|---|---|---|
| **Cibles** (domaines / IP / repos) | illimité | illimité | illimité | illimité |
| **Scans / jour** | 10 | 70 | 250 | **illimité** |
| **Scans concurrents** | 1 | 5 | 10 | 20 |
| **Targets max par batch** | 0 (désactivé) | 5 | 20 | 50 |
| **Modules** | 41 (sévérité ≤ HIGH) | les 139 | les 139 | les 139 |
| **Sévérité affichée** | HIGH max (CRITICAL masqués) | toutes | toutes | toutes |
| **Rétention findings** | 30 jours | 90 jours | 1 an | illimité |
| **Support** | KB + Discord public | email < 72 h | email < 24 h | Slack dédié < 8 h |
| **Rapports PDF** | watermark `Powered by Argos` | clean (sans watermark) | logo client en option | white-label complet |
| **Exports SARIF / CSV / JSON** | ❌ | ✅ | ✅ | ✅ |
| **CI/CD intégration (job SARIF)** | ❌ | ✅ | ✅ | ✅ |
| **API REST access** | ❌ | ✅ | ✅ | ✅ |
| **Watch** (re-scan continu) | ❌ | ❌ | ❌ | ✅ |
| **Chaînes d'attaque** | ❌ | ✅ | ✅ | ✅ |
| **IA fallback auto** (entre BYOK configurés) | ❌ | ❌ | ❌ | ✅ |
| **Comptes équipe (seats)** | 1 | 1 | 3 | 10 |

### Logique de gating à retenir pour SupportBot

- **CI/CD dès Pro** (strict minimum, **pas un argument premium**)
- **Watch** + **white-label complet** réservés Pro Max — c'est ce qui
  justifie le saut Team → Pro Max
- **Rétention** = un argument silencieux : Free 30 j force l'upgrade pour
  les utilisateurs qui veulent l'historique
- **CRITICAL masqués sur Free** = signal d'upgrade fort sans frustration
  excessive (le user voit qu'il y a quelque chose à voir au-dessus de HIGH)

---

## 3. Unité de facturation — `scans/jour`, pas `par cible`

**Au launch :** facturation en **scans/jour**, pas en cibles enregistrées.
C'est le modèle déjà en prod, géré par `core/quota.py`.

L'utilisateur peut scanner **n'importe quel domaine, IP ou repo** dans la
limite de son quota quotidien. **Pas de notion de « cible enregistrée »**
qui consomme un slot.

**Une cible inclut tout** : DAST + SAST + cloud + recon + network. Pas de
facturation séparée par catégorie de module.

### Réponse type pour SupportBot quand on demande « pourquoi pas par cible comme Acunetix ? »

> « Notre quota est en scans/jour pour qu'un même client puisse scanner
> plusieurs apps sans surfacturation. Marc qui a 5 sous-domaines paie le
> même prix Team que Marc qui en a 2. C'est plus simple à comprendre et
> ça évite la surfacturation des architectures multi-services. »

### Roadmap modèle « par cible »

Migration prévue **12-18 mois post-launch**, déclenchée par :
- > 100 abonnés payants actifs
- ET le modèle scans/jour montre ses limites (ex : abus type scrap massif,
  ou impossibilité de pricer correctement les très gros périmètres)

Pas avant. Refactor du modèle de facturation = 3-4 semaines de dev solo +
casse potentielle des comptes payants existants.

---

## 4. Free tier — funnel & friction calibrée

**Freemium permanent. Pas de trial.**

### Pourquoi pas trial 14 j

- Le trial force une décision binaire à J+14 alors que Marc n'a pas eu le
  temps de planifier un vrai scan
- Le trial brûle Thomas le freelance (notre evangelist) : sans accès
  permanent, il arrête d'utiliser et arrête de tweeter
- Free permanent = on devient « le truc gratos qui marche » dans la
  conscience des devs FR

### Limites Free volontairement frustrantes mais utiles

- 1 scan concurrent
- 10 scans / jour
- 41 modules sur 139 (les CRITICAL gated derrière Pro — voir [`argos_features.md`](argos_features.md) pour la liste exhaustive Free)
- Sévérité max affichée : **HIGH** — les CRITICAL sont masqués (signal
  d'upgrade fort sans frustrer le user qui ne voit pas ce qu'il rate)
- Pas d'export SARIF (= pas d'intégration CI possible → upgrade signal)
- PDF avec watermark `Powered by Argos — omnividens.fr`
- Rétention 30 jours

### Carte bleue au signup

**Non requise.** Friction zéro pour atteindre le « aha moment » (un PDF avec
un finding réel sur sa propre app). La carte bleue n'apparaît qu'au moment
où l'utilisateur clique « Upgrade ».

### Conversion attendue

**~3-5 % à 6 mois** Free → payant (chiffres standards SaaS B2B technique
freemium, à valider avec les vrais funnels en P19).

---

## 5. Annuel vs mensuel

### Réduction

**-20 %** sur l'engagement annuel (équivalent ~2,4 mois offerts).

| Tier | Mensuel | Annuel HT | Économie/an |
|---|---|---|---|
| Pro | 39 € | 372 € (= 31 €/mois) | 96 € |
| Team | 129 € | 1 240 € (= 103 €/mois) | 308 € |
| Pro Max | 249 € | 2 388 € (= 199 €/mois) | 600 € |

Choix de -20 % vs -17 % : c'est rond, lisible, et 0,4 mois supplémentaires
offerts ne change pas notre cash-flow significativement.

### Facturation

**En une fois à la souscription, débit immédiat.** Pas de mensualisation
sur 12.

Raisons :
- Solo, le cash-flow est vital — un client annuel à 1 240 € vaut mieux que
  12 paiements mensuels où il peut churner au mois 3
- Standard B2B (Stripe / Linear / Vercel le font tous)

### UI

Toggle annuel/mensuel sur la page Pricing. **Mensuel par défaut** au
premier load (le user voit le « petit » prix, le toggle annuel devient
une découverte = effet de gain).

---

## 6. Add-ons

### Actifs au launch

| Add-on | Prix | Disponible pour | Statut |
|---|---|---|---|
| **Scans hors quota** | 19 € / scan | Free uniquement | ✅ Actif |

> **Précision (figée — D-010) :** un user Pro / Team qui défonce son cap
> journalier est **rate-limité jusqu'à minuit J+1**, il **ne peut pas**
> acheter de scans hors quota. Pro Max est illimité par design. Le
> hors-quota Free reste un mini-add-on de transition Free→Pro : un user
> Free qui veut un 11ᵉ scan ce jour-ci paie 19 €, ressent la friction,
> comprend qu'à 39 €/mois il a 70 scans/jour. Vendre du hors-quota aux
> tiers payants brouillerait le signal d'upgrade Pro→Team→Pro Max, qui
> est notre principal moteur de conversion.
>
> **Garde-fou UX (à coder en P16 ou avant) :** quand un Pro/Team hit son
> quota, l'UI propose explicitement l'**upgrade au tier supérieur**, pas
> le hors-quota. Message canonique : « Tu as atteint 70 scans/jour.
> Upgrade à Team pour 250 scans/jour, ou attends 24 h. »

### Différés (à ouvrir post-launch)

| Add-on | Prix | Disponible pour | Trigger d'ouverture |
|---|---|---|---|
| **Audit manuel one-shot** par l'équipe Argos | 1 500 € / 1 journée | Tous tiers | Launch + 6 mois (planning fondateur stable) |
| **Data residency EU stricte** | +30 % du prix de base | Pro Max | Premier prospect qui le demande contractuellement |

### Inclus dans un tier (PAS un add-on à la carte)

- **White-label PDF** : logo client → Team / full white-label → Pro Max
- **Slack dédié** : Pro Max
- **Formation onboarding** : Pro Max
- **Intégrations Slack/Jira webhook** : Pro Max
- **SIEM custom (Splunk, Datadog, Elastic)** : hors scope launch, à rouvrir
  uniquement sur demande Custom contact sérieuse

### Règle absolue pour SupportBot

Toute demande d'add-on **récurrent et configurable** → on la pousse vers
le tier supérieur, **pas vers un add-on à la carte**. Add-on = ponctuel
uniquement.

---

## 7. Refund / cancellation / downgrade

| Cas | Politique |
|---|---|
| **Remboursement** | **14 jours sans condition** sur l'abonnement, peu importe le motif. Argument de confiance fort, utilisable en cold mail (« si ça te plaît pas, je rembourse »). Au-delà : pas de remboursement automatique mais cas par cas si abus manifeste de notre côté (bug bloquant, downtime). |
| **Cancellation mensuel** | Effet à **fin de la période en cours**. L'utilisateur garde l'accès jusqu'à la fin du mois payé. Pas de prorata cash-back (standard SaaS). |
| **Cancellation annuel** | Idem : fin de période = fin de l'année payée. Pas de remboursement au prorata sauf droit conso EU 14 j. Documenté en CGV. |
| **Downgrade Pro+ → Free** | Données conservées **90 jours** post-downgrade (re-upgrade possible sans perte). Au-delà : findings antérieurs purgés, mais les **PDF déjà générés restent téléchargeables 12 mois** depuis l'URL initiale (les liens ne se cassent pas). |
| **Downgrade Pro Max → Team / Team → Pro** | Conservation 90 j des features du tier supérieur en lecture seule, puis bascule réelle. **Watch désactivé immédiatement** (pour les downgrades depuis Pro Max). |
| **Trial expiré** | N/A — pas de trial, Free permanent par défaut. |
| **Compte abandonné** (zéro scan 6 mois Pro+) | Email de relance → pause d'abonnement avec accord du user → bascule Free → suppression définitive 90 j après bascule Free. |
| **Abus de la garantie 14 j** (souscrit → scan 30 cibles en 14 j → demande remboursement) | **Bannissement email + IP + carte**. Documenté en CGV. |

---

## 8. Comparaison concurrence

### Chiffres connus avec certitude

| Concurrent | Plan | Prix mensuel équivalent | Source |
|---|---|---|---|
| Acunetix Online | Standard 1 site | **350 €** ($4 500/an) | datasheet 2024 |
| Acunetix Premium | 5 sites | 580 € ($7 000/an) | datasheet 2024 |
| Detectify | Surface Monitoring | ~400 € | landing publique |
| Detectify Crowdsource | Premium | ~800 € | leaks LinkedIn / sales-quote |
| Intruder | Essential | ~95 € ($113) | landing publique |
| Intruder | Pro | ~165 € ($192) | landing publique |
| Intruder | Premium | ~390 € ($441) | landing publique |
| **Burp Suite Pro** | 1 user (outil manuel — pas comparable direct) | **39 €** (475 €/an) | site PortSwigger |
| Pentest-Tools | Pro | ~200 € ($223) | landing publique |
| Pentest-Tools | Advanced | ~390 € ($429) | landing publique |
| Probely | Pro | ~200 € | landing publique |

### Inconnus / à confirmer

- **Pentera** : Enterprise sur devis uniquement. Rumeur ~50-150 k€/an mais
  jamais vu de prix public
- **Cobalt** (Pentest as a Service) : variable selon scope, minimum
  ~5-20 k€/an
- **Snyk** : Team $25/dev/mois mais c'est SAST → **pas comparable direct**,
  on n'attaque pas leur segment

### Calibrage Argos vs concurrence

| Tier Argos | Périmètre | Concurrent direct | Position |
|---|---|---|---|
| **Pro 39 €** | 1 user, 139 modules | Burp Pro 39 € (manuel), Intruder Essential 95 € | équivalent Burp (justifié : on est SaaS, pas outil manuel), **-59 % vs Intruder Essential** ✅ |
| **Team 129 €** | 3 users, 250 scans/jour | Intruder Pro 165 €, Probely 200 € | **-22 % vs Intruder Pro, -36 % vs Probely** ✅ |
| **Pro Max 249 €** | 10 users, illimité | Intruder Premium 390 €, Acunetix Standard 350 € | **-36 % vs Intruder Premium, -29 % vs Acunetix Standard** ✅ |

### Phrase clinchante (à utiliser dans tous les canaux SupportBot / OutboundBot)

> **« 0 faux positif et 139 modules entre 39 € et 249 €. Acunetix démarre
> à 350 € pour 1 site. »**

Variante Free vs payant (à utiliser en cold call quand le prospect demande
le free tier) : **« Free : 41 modules sévérité ≤ HIGH. Tous les tiers
payants : 139 modules, sans limite de sévérité. »**

C'est la formule canonique. La grille tient le **20-40 % moins cher**
partout sur le segment SaaS comparable.

---

## 9. Devises, TVA, Stripe Tax

| Décision | Choix au launch | Raison |
|---|---|---|
| **Devises** | EUR uniquement | Cohérent FR-first. Afficher USD/GBP au launch dilue le focus + pose des questions de FX margin. À rouvrir 6-12 mois quand on attaque l'EN. |
| **HT vs TTC** | **HT par défaut** (mention « TVA en sus » bien visible page Pricing) | Standard B2B. Marc et Sarah comptent en HT. Afficher TTC inflate visuellement nos prix face aux concurrents qui affichent HT. |
| **Stripe Tax** | ✅ Activé dès le launch | Auto-collecte TVA UE selon pays de facturation, gestion automatique du reverse charge B2B intra-UE, conformité OSS. Évite de gérer manuellement 27 taux UE différents. Déjà activé dans le code (`tax_id_collection={"enabled": True}` dans `stripe_service.create_checkout_session`). |
| **VAT ID au signup** | ✅ Activé pour boîtes UE | Boîte FR/BE/DE avec VAT ID valide → reverse charge automatique (TVA = 0, l'acheteur la déclare chez lui). Sans VAT ID → TVA du pays appliquée. Déjà activé dans le code. |
| **Particuliers / freelance UE sans VAT ID** | TVA française 20 % appliquée d'office | Conformité, pas négociable. Thomas qui paie en perso paie 39 € + 20 % = **46,80 € TTC**, et il le sait. |
| **Hors-UE (US, UK post-Brexit, Asie)** | Pas de TVA collectée par défaut au launch | Stripe Tax peut gérer US sales tax si on active, mais c'est complexe (par État). À rouvrir quand on aura > 10 % de revenus US. UK reverse charge B2B identique à l'UE. |

---

## 10. Glossaire pricing-relevant

Définitions courtes pour que SupportBot puisse répondre aux questions
pricing sans halluciner. **Détail technique complet → voir
[`argos_features.md`](argos_features.md)** (P3-M2 fichier 4).

| Terme | Définition courte (figée — D-012) |
|---|---|
| **Watch** | Re-scan automatique d'une cible à intervalle configurable (6 h / 24 h / hebdo) avec alerte sur les changements : nouveau finding ≥ sévérité min, finding RESOLVED qui réapparaît (régression), score de risque global qui se dégrade. Canaux : Slack webhook, email, push dashboard. Historique conservé en timeline. **Pro Max uniquement.** |
| **Chaînes d'attaque** | À la fin de chaque scan, l'agent IA corrèle les findings et identifie les **séquences exploitables ensemble** au-delà des CVSS individuels. Chaque chaîne = score de criticité (souvent ≥ max des findings individuels), PoC step-by-step, findings constitutifs linkés, remédiation pointant le maillon faible. **Pro / Team / Pro Max.** Nécessite l'IA en mode corrélation (BYOK user). |
| **IA fallback auto** | Bascule automatique entre les **clés API que le user a configurées** (≥ 2 providers, ex : Anthropic + OpenAI) en cas de rate-limit ou erreur 503. Si tous les providers du user échouent → scan continue en mode dégradé sans corrélation IA. **Aucune clé serveur Argos en backup** (D-011) — préserve la promesse « 0 € de SaaS récurrent en plus ». **Pro Max uniquement.** |
| **BYOK** | Bring Your Own Key. L'utilisateur fournit sa clé Claude / OpenAI / Google dans Settings ; les appels IA se font avec sa clé, on ne touche pas à ses données. **Tous tiers.** Pour Pro Max, configurer ≥ 2 providers est nécessaire pour que l'IA fallback auto soit utile. |
| **Rétention findings** | Durée pendant laquelle les findings d'un scan restent consultables dans le dashboard. Au-delà : findings purgés, mais les PDF déjà générés restent téléchargeables 12 mois. |
| **Finding unitaire** vs **Chaîne d'attaque** | Finding unitaire = une vuln isolée (« XSS sur `/search` »). Chaîne d'attaque = un graphe corrélé qui exploite plusieurs findings ensemble pour atteindre un impact business (RCE, account takeover, exfiltration). |
| **Watch** vs **Chaînes d'attaque** | Souvent confondus. Watch = entre les scans, surveille dans le temps une cible donnée (Pro Max only). Chaînes d'attaque = pendant un scan, corrèle les findings de ce scan (Pro+). Voir D-012 pour le tableau différentiel complet. |

---

## 11. Réponses-types pricing pour SupportBot

### « C'est combien ? »

> « 4 plans : Free (gratuit forever), Pro 39 €/mois, Team 129 €/mois,
> Pro Max 249 €/mois. -20 % en annuel. Tous incluent les 139 modules
> (sauf Free, limité à 41 modules sévérité ≤ HIGH). Tu peux signer en
> self-serve depuis [omnividens.fr/pricing](https://omnividens.fr/pricing). »

### « Pourquoi pas par cible comme Acunetix ? »

> « Notre quota est en scans/jour. Tu peux scanner autant de domaines, IP
> ou repos différents que tu veux dans ton quota quotidien. Marc qui a 5
> sous-domaines paie le même prix Team que Marc qui en a 2. »

### « Quelle différence Team vs Pro Max ? »

> « Team (129 €) couvre les besoins d'une équipe scaleup classique : 250
> scans/jour, 3 seats, CI/CD intégré, rapports clean. Pro Max (249 €)
> rajoute le **Watch** (re-scan continu hebdo avec notif des nouveaux
> findings), le **white-label complet**, l'**IA fallback** (analyse IA
> sans avoir à fournir une clé BYOK), 10 seats, et le support Slack
> dédié < 8 h. Si t'es une fintech / healthtech qui prépare une certif,
> Pro Max est fait pour toi. »

### « Vous remboursez ? »

> « 14 jours sans condition, peu importe le motif. Tu cliques annuler dans
> ton compte ou tu m'écris à `contact@omnividens.fr`, je rembourse. »

### « Vous avez un Enterprise ? »

> « Pas de plan Enterprise public au launch. Si tu as besoin d'un SLA
> contractuel, d'un MSA, ou de data residency EU stricte, on fait du
> custom à partir de 5 000 €/mois. Écris à `contact@omnividens.fr` avec
> tes besoins, je reviens vers toi sous 48 h. »
