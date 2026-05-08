# Argos vs concurrence — référentiel comparatif

> **Source de vérité** pour SupportBot, ChatBot widget, OutboundBot,
> ContentBot, page Pricing publique et toute comm comparative. Si un autre
> fichier KB ou une page publique formule une comparaison différemment,
> **ce fichier prime** — créer une PR pour aligner.
>
> Source : interview fondateur en P3-M2 (2026-05-08), croisée avec
> [`pricing.md`](pricing.md) § 8 (grille prix concurrence) et
> [`argos_features.md`](argos_features.md) § 3 (différenciateurs sourcés
> au code).

---

## 1. Positionnement canonique

### 1.1 Phrase produit canonique

À utiliser en cold call, page Pricing publique, premier message
ChatBot, abstract de blog post comparatif :

> **« Argos est le scanner DAST automatisé qui transforme votre surface
> web en chaînes d'attaque exploitables — pas une liste de findings — à
> partir de 39 €/mois, sans pentester en interne. »**

Pourquoi cette formulation marche :

- **« Chaînes d'attaque exploitables vs liste de findings »** = le
  différenciateur n°1 sourcé au code (Correlator IA, cf.
  [`argos_features.md` § 4.3](argos_features.md#43-cha%C3%AEnes-dattaque-correlator))
- **« Sans pentester en interne »** = cible directement
  startups / PME / SaaS qui n'ont pas le budget d'un pentester
  full-time
- **Le prix est mentionné mais pas l'argument central** → évite la
  redondance avec la phrase clinchante prix de
  [`pricing.md` § 8](pricing.md#phrase-clinchante-%C3%A0-utiliser-dans-tous-les-canaux-supportbot--outboundbot)

### 1.2 Variantes par contexte

**Pour un canal techie (DM LinkedIn, Mastodon, blog dev) :**
> « Le premier scanner DAST avec corrélation IA multi-provider
> (Anthropic / OpenAI / Google / DeepSeek BYOK) qui livre un
> kill chain narratif au lieu d'une liste CSV. »

**Pour un canal RSSI / Head of Sec (cold mail, cas d'usage long-form) :**
> « Argos est le bon choix pour les SaaS / éditeurs B2B qui veulent la
> couverture d'un Burp + Acunetix combinés, sans le prix entreprise et
> sans recruter un pentester. »

**Pour la phrase clinchante prix** (déjà figée, voir
[`pricing.md` § 8](pricing.md#phrase-clinchante-%C3%A0-utiliser-dans-tous-les-canaux-supportbot--outboundbot)) :
> « 0 faux positif et 139 modules entre 39 € et 249 €. Acunetix démarre
> à 350 € pour 1 site. »

### 1.3 Avec qui on se compare — et avec qui on ne se compare pas

**Concurrents directs (segment DAST + scan automatisé externe) :**
**Acunetix**, **Detectify**, **Burp Suite Pro** (cas particulier — outil
manuel), **Intruder**, **Pentest-Tools**, **Probely**, **Pentera** (cas
particulier — segment enterprise BAS).

**Hors comparable direct** : Snyk, Semgrep, SonarQube, Veracode SAST,
Sonatype. Ce sont des produits **SAST** ou **SCA** focused, pas DAST.
Argos a un complément SAST (14 modules sur 139, ~10 %) mais ne
prétend pas remplacer leur cœur de métier
(cf. [`tone_of_voice.md` § 1.1](tone_of_voice.md#11-pitch-de-r%C3%A9f%C3%A9rence-30-secondes)). Détail
en [§ 7](#7-hors-comparable-direct--snyk-semgrep-sonarqube-veracode).

### 1.4 Matrice synthétique prix × périmètre

> Tous les prix sont mensuels HT, sources pricing publiques + datasheets
> 2024 (cf. [`pricing.md` § 8](pricing.md#8-comparaison-concurrence) pour
> les sources détaillées).

| Concurrent | Plan entry | Plan typique | Plan top | Périmètre | Type |
|---|---:|---:|---:|---|---|
| **Argos Pro** | 39 € | — | — | 139 modules, 1 user, 70 scans/j | DAST automatisé + IA-corrélation |
| **Argos Team** | — | 129 € | — | 139 modules, 3 users, 250 scans/j | DAST automatisé + IA-corrélation |
| **Argos Pro Max** | — | — | 249 € | 139 modules, 10 users, illimité | DAST automatisé + IA-corrélation + Watch |
| Acunetix Online | 350 € | — | 580 € | 1-5 sites, ~100 modules | DAST automatisé legacy |
| Detectify | — | ~400 € | ~800 € | Surface monitoring + Crowdsource | DAST + research community |
| Intruder | ~95 € | ~165 € | ~390 € | Cloud-focus, ~80 modules | DAST automatisé |
| Burp Suite Pro | 39 € | — | — | Outil manuel pentester | DAST manuel + extensions |
| Pentest-Tools | — | ~200 € | ~390 € | DAST + recon | DAST automatisé |
| Probely | — | ~200 € | — | DAST API + web | DAST automatisé API-first |
| Pentera | — | — | 50-150 k€/an | BAS + red-team automated | Breach Attack Simulation |
| Cobalt | — | — | ≥ 5-20 k€/an | Pentest as a service | Pentest distributed humain |

**Lecture rapide** : Argos Pro 39 € est l'**équivalent prix Burp Pro**
(mais SaaS automatisé), **-59 % vs Intruder Essential 95 €** sur
périmètre supérieur. Argos Team 129 € est **-22 % vs Intruder Pro 165 €**
et **-36 % vs Probely 200 €**. Argos Pro Max 249 € est **-36 % vs
Intruder Premium 390 €** et **-29 % vs Acunetix Standard 350 €**.

---

## 2. Argos vs Acunetix

Le concurrent le plus cité, le duel le plus fréquent en cold call. La
crédibilité Argos passe par **reconnaître honnêtement les forces
Acunetix avant de présenter les forces Argos**. Un prospect qui sent
qu'on minimise un concurrent connu décroche.

### 2.1 Forces relatives Acunetix (à reconnaître honnêtement)

1. **Maturité produit 20+ ans.** UI stable, workflows éprouvés, doc
   exhaustive, formations certifiées. Argos a 1 an de refonte v2 dans
   les pattes, pas 20.
2. **Intégrations enterprise packagées.** Jira / ServiceNow / Jenkins /
   GitHub Enterprise / Azure DevOps natifs avec mappings champ-à-champ.
   Argos a une API REST propre mais pas de connecteurs packagés au
   launch.
3. **Authentication recorder visuel.** Pour les login sequences
   complexes (SSO multi-step, MFA, captcha contournable manuellement),
   Acunetix a un recorder GUI mature. Argos demande une recipe JSON
   manuelle (`auth_recipe`).
4. **AcuMonitor — infra OOB dédiée.** Acunetix opère son propre serveur
   OOB depuis ~10 ans, robuste et géo-distribué. Argos s'appuie sur
   des services OOB tiers (dnslog.cn / Burp Collaborator-like) — plus
   fragile en théorie.
5. **Certification PCI-ASV.** Acunetix peut signer un rapport pour
   audit PCI-ASV trimestriel. Argos non au launch — c'est un projet
   de cert moyen-terme (12-18 mois post-launch, conditionné à un
   premier prospect qui le demande sérieusement).

### 2.2 Forces relatives Argos

Au-delà des 5 différenciateurs sourcés au code (cf.
[`argos_features.md` § 3](argos_features.md#3-zoom-sur-25-30-modules-embl%C3%A9matiques)
et [§ 4](argos_features.md#4-couche-ia-corr%C3%A9lation)) :

1. **Prix structurel 10-20× moins cher.** Argos Pro 39 €/mois vs
   Acunetix Online ~350 €/mois (entry tier). Pour un SaaS / PME tech
   sans budget enterprise, c'est l'argument décisif.
2. **Transparence formule risk score.** Argos publie son code :
   `Σ severity_weight + poc × 2 + chains × 3` dans
   [`argos_features.md` § 4.5](argos_features.md#45-risk-score-a-f-d%C3%A9terministe).
   Acunetix sort un score blackbox — un RSSI ne peut pas le contester
   ni le défendre en audit.
3. **Calibration anti-FP industrielle.** 66 bugs documentés et corrigés
   en post-v2 (cf. `ARGOS_MODULE_BUGS.md` côté SecHunter). Pas une
   promesse marketing, du code.
4. **Stack moderne.** Python 3.12 / FastAPI / async-first / mypy strict /
   6700+ tests. Acunetix = legacy Windows/.NET historique avec dette
   technique accumulée.
5. **BYOK multi-provider IA.** Pas de lock-in OpenAI/Anthropic — Argos
   accepte Anthropic / OpenAI / Google / DeepSeek selon ce que le
   client a déjà signé (cf.
   [D-011](../../docs/DECISIONS.md#d-011--ia-fallback-auto-pro-max--byok-seul-pas-de-cl%C3%A9-serveur-argos)).
   Acunetix a juste son propre engine IA, point.
6. **Compliance mapping triple framework article-par-article.**
   PCI-DSS 4.0 (refs précis) + RGPD (5 articles : 5(1)(f), 25, 32, 33,
   34) + OWASP 2021. Acunetix couvre PCI/OWASP mais pas RGPD
   article-par-article (cf.
   [`argos_features.md` § 4.6](argos_features.md#46-compliance-mapping-triple-framework)).

### 2.3 Migration Acunetix → Argos : recommandée si…

**OUI migration recommandée si :**

- SaaS startup ou PME tech, **budget total sécurité < 5 000 €/an**
- Équipe 1-3 dev/sec, **pas de RSSI temps plein**
- Pas besoin de **tampon PCI-ASV officiel** sur le rapport
- Pas d'**intégrations Jira / ServiceNow** workflow-lourdes (l'API
  REST suffit)
- Veut **comprendre comment le scanner décide** (pas de blackbox
  acceptée)

**NON migration recommandée si :**

- **Enterprise** avec workflow ServiceNow / Jira figé sur Acunetix
  depuis ≥ 2 ans (coût de migration > économie de licence)
- **Audit PCI-ASV trimestriel** qui exige tampon scanner certifié
- **Plus de 50 cibles à scanner en CI/CD** avec policy YAML versionné
  → Argos arrive sur ce terrain mais Acunetix Premium est plus mature
  aujourd'hui

> **Réponse SupportBot canonique** quand un prospect Acunetix Premium
> (5+ k€/an, équipe sécu structurée) hésite à migrer :
> « Honnêtement, sur ton profil Acunetix Premium fait le job. Migre vers
> Argos quand tu auras besoin (a) de comprendre et défendre la formule
> du score risk en audit, (b) de la corrélation IA en chaînes d'attaque,
> ou (c) de réduire ta facture sécurité par 10. Si aucun des 3, reste sur
> Acunetix — on n'a pas le tampon PCI-ASV officiel et nos intégrations
> Jira/ServiceNow sont moins matures que les leurs. »

---

## 3. Argos vs Detectify

Detectify se positionne sur le marketing « **our researchers find it
before hackers do** » avec un programme **Crowdsource** où des
chercheurs externes contribuent les modules de scan.

### 3.1 L'angle Crowdsource — latence factuelle

**Réponse canonique** quand un prospect cite l'argument Crowdsource :

> « Detectify Crowdsource c'est super pour découvrir des CVE 0-day rares,
> mais ça crée une latence : entre la disclosure d'une CVE et le moment
> où un chercheur Crowdsource code le module, il se passe **des semaines
> à des mois — sans SLA**. Argos a 67 sessions de refonte v2 + 16 batches
> post-v2 documentés en open dans le repo (66 bugs identifiés et
> corrigés). C'est de la qualité industrielle maintenue, pas du
> best-effort communautaire. Et l'IA Strategist adapte la stratégie
> d'attaque à chaque cible (CMS, WAF, stack) — Detectify ne fait pas ça. »

**À éviter** :

- ❌ « On a aussi des chercheurs externes » — faux, casse la trust
  immédiatement
- ❌ « Crowdsource = bullshit » — disparagement, contre-productif

### 3.2 L'angle prix-valeur

**Detectify Pro ~400 €/mois** (Surface Monitoring) vs **Detectify
Crowdsource Premium ~800 €/mois**. Argument à utiliser :

> « Detectify Pro, c'est 400 €/mois pour un scanner avec un pipeline
> humain externe sans SLA. Argos Pro, c'est 39 €/mois pour 139 modules
> maintenus + IA-corrélation + Watch en Pro Max. Le ratio prix/valeur
> est ~10× pour les profils SaaS/PME, et tu gardes la maîtrise complète
> du scope que tu scannes. »

### 3.3 Quand Detectify est meilleur

À reconnaître honnêtement (selon profil prospect) :

- Si la cible principale est **bug bounty discovery** (chercher des
  CVE 0-day émergentes en surface), Detectify Crowdsource a un edge
  difficile à contester (chercheurs incentivés à creuser tôt)
- Si l'équipe **n'a aucune maturité sécu** et veut un truc « one-click
  no config », Detectify est plus proche du grand public que Argos
  qui demande de comprendre les modules

---

## 4. Argos vs Burp Suite Pro — cas particulier

**Argos Pro 39 € = Burp Pro 39 €.** Mais Burp est un **outil manuel**
pour pentester, pas un scanner automatisé. Confusion fréquente à
dissiper.

### 4.1 Cadrage canonique : COMPLÉMENTAIRES, pas remplacement

**Pitch canonique :**

> « Burp Pro est l'outil n°1 du pentester manuel pour explorer une
> cible inconnue, exploiter de la logique métier exotique, faire des
> PoC custom. C'est de l'artisanat. Argos automatise le scope
> répétitif — les 139 vulns connues qu'il faut scanner sur ta prod
> chaque nuit, en continu, sans qu'un humain perde son temps. Les deux
> sont complémentaires : Argos balaye en continu (cron / Watch mode
> Pro Max), ton pentester (toi-même ou un externe ponctuel) sort Burp
> pour la logique métier qu'aucun scanner ne peut couvrir. À 39 € + 39 €
> = 78 €/mois tu as les deux. »

### 4.2 Pourquoi NE PAS positionner « Argos remplace Burp »

Trois raisons cumulées :

1. **C'est faux techniquement.** Burp couvre des cas qu'aucun scanner
   automatisé ne fera bien : logique métier custom, race conditions
   exotiques, attaques chainées sur-mesure, exploration manuelle des
   endpoints non discoverables.
2. **Ça vexe la communauté pentester.** Les pentesters sont les early
   adopters d'Argos et nos amplificateurs naturels (blog, Mastodon,
   Discord infosec). Si Argos se positionne comme « remplacement de
   Burp », ils refusent par principe — même si le produit est bon.
3. **Ça empêche un canal de distribution gratuit.** Un pentester
   freelance qui fait 5 audits/mois peut **vendre Argos en upsell à
   ses clients** (« je fais le pentest manuel + tu gardes Argos en
   monitoring continu »). C'est un canal organique zéro CAC qui
   disparaît si on positionne contre Burp.

### 4.3 Réponse SupportBot canonique

> Prospect : « J'ai déjà Burp Pro à 39 €/mois, pourquoi je prendrais
> Argos en plus ? »
>
> SupportBot : « Burp et Argos couvrent deux choses différentes. Burp
> est ton outil quand tu prends 4 heures pour explorer manuellement une
> nouvelle cible et exploiter une logique métier. Argos, c'est le scan
> qui tourne tous les soirs sur ta prod sans toi pour détecter les
> régressions et les nouvelles vulns connues. Le ratio coût-bénéfice :
> 39 €/mois pour récupérer le temps que tu passerais à relancer Burp
> en manuel chaque semaine sur 30 endpoints. Si tu fais déjà ce scan
> régulier en CI/CD avec un script Burp, tu n'as pas besoin d'Argos.
> Sinon, Argos est complémentaire — pas un remplacement. »

---

## 5. Argos vs Pentera et le segment enterprise

**Pentera** est positionné sur le **BAS** (Breach Attack Simulation) /
**red-team automated** à 50-150 k€/an. Argos Custom contact démarre à
5 000 €/mois (= 60 k€/an HT).

### 5.1 Position canonique : besoin différent, pas concurrence directe

**Pitch canonique :**

> « Pentera et Argos servent des besoins différents. Pentera fait du BAS
> / red-team automatisé interne — il simule un attaquant qui a déjà un
> pied dans ton réseau et lateralise. Argos fait du DAST automatisé
> externe + IA-corrélation — il scanne ta surface web exposée. Si tu as
> les deux besoins, deux outils. Si tu n'as que le besoin DAST (cas
> 90 % des SaaS), Argos Custom à 60 k€/an est 40-50 % moins cher qu'une
> licence Pentera complète, et notre DAST est plus profond que celui de
> Pentera (qui n'en fait pas son focus). »

### 5.2 Pourquoi pas une attaque frontale Pentera

Position humble et technique, pas offensive. Trois raisons :

1. **Cohérence avec [§ 5.1 antimatière](argos_features.md#51-pas-de-bas--breach-attack-simulation)**
   d'`argos_features.md` qui dit explicitement « Argos ne fait pas de
   BAS ». Une attaque frontale contredirait ce positionnement.
2. **Crédibilité technique.** Un prospect Pentera connaît bien le
   marché — comparer Pentera à Argos en frontal serait perçu comme
   « je compare des poires et des pommes » et casserait la trust.
3. **Position humble = signal de maturité.** Reconnaître ce que fait
   Pentera (simulation adversariale interne) montre qu'on connaît le
   marché. C'est ce que ferait un sales senior.

### 5.3 Quand Argos ET Pentera ensemble

Quand le prospect a **les deux besoins** (DAST externe **et** BAS
interne) — typiquement Sarah Head of Sec dans une boîte fintech /
santé / défense qui prépare une certif :

> « Argos pour le DAST + Pentera pour le BAS. Ce sont deux briques
> complémentaires de votre stack sécurité. Sur le DAST, Argos est plus
> profond et 5-10× moins cher. Sur le BAS, on cède la place à Pentera
> qui en fait son cœur de métier. »

---

## 6. Argos vs Intruder

**Intruder** est probablement le concurrent **le plus proche en
prix-périmètre** : Essential ~95 €, Pro ~165 €, Premium ~390 €. C'est
aussi un scanner DAST automatisé cloud-focus.

### 6.1 Calibrage prix-tier

| Argos | Prix | Intruder équivalent | Prix | Écart |
|---|---:|---|---:|---|
| Pro | 39 € | Essential | ~95 € | **-59 %** |
| Team | 129 € | Pro | ~165 € | **-22 %** |
| Pro Max | 249 € | Premium | ~390 € | **-36 %** |

Argos est moins cher sur les 3 tiers comparables, périmètre équivalent
ou supérieur (139 modules vs ~80 chez Intruder).

### 6.2 Différenciateurs Argos vs Intruder

Au-delà du prix :

1. **Chaînes d'attaque (Correlator IA)** — Intruder n'a pas de
   corrélation IA des findings en kill chain narratif
   (cf. [`argos_features.md` § 4.3](argos_features.md#43-cha%C3%AEnes-dattaque-correlator)).
   Intruder sort une liste classique CVE par CVE.
2. **Stratégie pré-scan adaptative (Strategist IA)** — Intruder applique
   les mêmes modules sur toutes les cibles. Argos détecte
   WAF/CMS/stack et adapte la stratégie (cf.
   [`argos_features.md` § 4.2](argos_features.md#42-strategist--strat%C3%A9gie-pr%C3%A9-scan-adaptative)).
3. **BYOK multi-provider IA** — Intruder n'a pas d'IA, pas la question.
4. **Compliance mapping article-par-article** — Intruder couvre OWASP
   et PCI mais pas RGPD article-par-article.
5. **Watch mode** (Pro Max) — Intruder a du monitoring continu mais pas
   avec timeline diff signature stable + détection régression auto
   comme Argos (cf.
   [`argos_features.md` § 4.4](argos_features.md#44-watch--surveillance-continue-pro-max-only)).

### 6.3 Quand Intruder peut être le bon choix

À reconnaître honnêtement :

- Si l'équipe **veut un scanner cloud-focus exclusivement** (AWS / GCP /
  Azure infra scan sans web), Intruder a un focus historique sur ce
  segment — Argos couvre cloud mais avec un focus DAST web prioritaire
- Si la cible est une **petite équipe DevOps** habituée aux outils
  Crowdstrike / Datadog (UX similaire SaaS infra), Intruder est dans
  cet univers UX — Argos est plus orienté pentester / dev sec

---

## 7. Hors comparable direct — Snyk, Semgrep, SonarQube, Veracode

**On ne se compare pas à eux.** Ce sont des produits **SAST** ou **SCA**
focused, pas DAST. Argos a un complément SAST (14 modules sur 139,
~10 %) qui couvre les CVE via OSV.dev et les secrets, mais ne prétend
pas remplacer leur cœur de métier.

### 7.1 Argument à utiliser quand un prospect demande la comparaison

> « Snyk / Semgrep / SonarQube font du SAST — ils analysent ton code
> source en statique. Argos fait du DAST — on teste ton appli en
> runtime depuis l'extérieur sans accès au code. C'est complémentaire,
> pas concurrent. Notre complément SAST (14 modules sur 139) couvre
> les secrets hardcodés et les dépendances avec CVE via OSV.dev — pour
> du SAST plus profond avec licence policy enforcement et patch
> suggestion auto-PR, on redirige vers Snyk Pro. »

### 7.2 Redirection vers le produit adapté

| Besoin | Produit canonique | Pourquoi pas Argos |
|---|---|---|
| **SAST profond avec licence policy** | Snyk Pro | Pas de licence policy enforcement dans Argos |
| **SAST custom rules** | Semgrep | Argos n'a pas de rule engine custom |
| **SCA exhaustif tous écosystèmes** | Snyk / Dependabot / Renovate | Argos couvre OSV.dev mais pas tous les écosystèmes |
| **Code quality + sécu unifiés** | SonarQube | Argos est sécu-only |
| **Static + Dynamic combined enterprise** | Veracode | Argos est DAST seul |

Cf. [`argos_features.md` § 5.3 antimatière](argos_features.md#53-pas-de-sca-full-%C3%A9cosyst%C3%A8me-snyk--dependabot-grade)
pour le détail des hors-scope SCA.

---

## 8. Anti-ICP comparatif — qui ne doit PAS choisir Argos

Le pendant honnête de l'ICP. Précieux pour SupportBot qui doit éconduire
un mauvais lead avant qu'il signe et churn à M+2.

### 8.1 Cas n°1 — Enterprise CI/CD-heavy

**Profil :** Boîte enterprise avec 50+ scans/jour à orchestrer, policy
YAML versionné, workflow ServiceNow / Jira figé sur Acunetix Premium /
Veracode depuis ≥ 2 ans.

**Recommandation :** **Reste sur ton outil actuel.**

**Pourquoi Argos n'est pas adapté aujourd'hui :**

- Intégrations enterprise mature (ServiceNow / Jira / SSO SAML
  enterprise) pas au niveau au launch
- Support 24/7 avec SLA contractuel — Argos Pro Max offre Slack < 8 h,
  pas du 24/7 enterprise
- Certifications produit (PCI-ASV, ISO certifié) — Argos n'a pas
  encore le tampon

**Risque si l'enterprise signe quand même :** churn à M+2-M+3 sur
intégrations manquantes, perte de trust, mauvais review en réseau.

### 8.2 Cas n°2 — Équipe avec maturité sécu = 0

**Profil :** Petite équipe dev (1-3 personnes) sans culture sécu, qui
veut un scan **one-click sans config**.

**Recommandation :** **Detectify ou Probely.**

**Pourquoi Argos n'est pas adapté :**

- Argos demande de comprendre les modules (139, c'est beaucoup pour un
  débutant), configurer l'authent (recipe JSON), lire les findings
  techniques avec PoC
- C'est un produit **dev sec / pentester-friendly**, pas grand public

**Quand bascule vers Argos :** quand l'équipe a 1 an de maturité sécu
(quelqu'un qui sait lire un CVE + un PoC) et un budget pour optimiser
la facture sécurité.

### 8.3 Cas n°3 — Audit PCI-ASV trimestriel obligatoire

**Profil :** E-commerce ou fintech qui a une obligation PCI-DSS avec
**audit ASV trimestriel signé**.

**Recommandation :** **Acunetix / Tenable / Qualys.**

**Pourquoi Argos n'est pas adapté :**

- Argos ne signe pas de rapport ASV officiel au launch
- Le compliance officer du client exige le tampon scanner certifié
  (ce n'est pas négociable côté audit)

**Quand bascule vers Argos :** quand le PCI-ASV n'est plus une
contrainte (out-of-scope changé) ou quand Argos obtient la
certification (12-18 mois post-launch, conditionné à un volume de
demandes).

### 8.4 Cas n°4 — Besoin = pentest applicatif mobile

**Profil :** Studio mobile iOS / Android qui veut scanner ses APK / IPA.

**Recommandation :** **MobSF (open-source) ou NowSecure / Veracode
Mobile.**

**Pourquoi Argos n'est pas adapté :**

- Argos ne couvre **pas le mobile** (cf.
  [`argos_features.md` § 5.4 antimatière](argos_features.md#54-pas-de-mobile-masa--ios--android))
- Aucun module APK / IPA, aucun runtime mobile (Frida, Objection)

### 8.5 Cas n°5 — Use case = bug bounty solo individuel

**Profil :** Bug hunter individuel qui scanne des cibles ad-hoc dans
des programmes BugCrowd / HackerOne.

**Recommandation :** **Burp Pro suffit (39 €).**

**Pourquoi Argos n'est pas adapté :**

- Argos brille en **monitoring continu de TES assets**, pas en
  discovery one-shot pour bug bounty
- Pour scanner une cible une fois en exploration manuelle, Burp Pro +
  Nuclei + recon home-made est plus adapté
- Argos = produit pour ton infra à toi, pas pour les cibles
  bug-bounty d'un programme tiers

---

## 9. Tableau récapitulatif par concurrent

Vitamine pour cold call rapide. À garder ouvert dans un onglet quand on
écrit un cold mail ou qu'on prépare une démo.

| Concurrent | Quand on gagne | Quand on perd | Phrase clé |
|---|---|---|---|
| **Acunetix** | SaaS / PME tech, budget < 5k€/an, transparence formule risk score, RGPD article-par-article | Enterprise CI/CD-heavy, audit PCI-ASV obligatoire, intégrations Jira figées | « 10× moins cher avec une formule risk score que tu peux défendre en audit » |
| **Detectify** | SaaS qui veut maîtrise du scope, prix-valeur 10× | Bug bounty discovery focus, équipe 0 maturité sécu | « 39 €/mois vs 400 €/mois pour 139 modules + IA, pas de pipeline humain externe sans SLA » |
| **Burp Suite Pro** | Complément, pas concurrent | Si le user fait déjà tout en CI/CD avec script Burp | « Argos automatise ce que tu relances chaque semaine en manuel. 78 €/mois pour les deux. » |
| **Intruder** | Périmètre Web/DAST plus profond, IA-corrélation, prix -22 à -59 % | Cloud-focus exclusif AWS/GCP/Azure | « 139 modules vs leur 80, IA-corrélation incluse, -36 % au tier Pro Max » |
| **Pentera** | Si le besoin est DAST seul (90 % des SaaS) — 40-50 % moins cher | Si le besoin réel est BAS / red-team | « DAST profond à 60 k€/an Custom contact, sans le BAS qu'on ne fait pas » |
| **Pentest-Tools** | Périmètre comparable, IA-corrélation différenciant | Si le user veut juste de la recon basique | « Ratio prix/profondeur similaire, on rajoute la corrélation IA et le Watch en Pro Max » |
| **Probely** | Web + API, prix -36 % | Si l'user a besoin d'une UX API-first ultra-spécifique | « Nous aussi web + API, à 129 €/mois Team avec 3 seats inclus vs leur 200 € » |
| **Snyk / Semgrep / SonarQube / Veracode** | Hors comparable | — | « Pas concurrents — eux SAST, nous DAST. Complémentaires. » |

---

## 10. Règles de comm comparative (anti-disparagement)

Pour SupportBot, ChatBot, OutboundBot et toute comm publique. **Ces
règles tiennent même sans avocat dans la boucle**, parce qu'elles sont
factuelles, pas juridiques. Pour les cas limites légaux (page Pricing
publique, comparatif en blog post indexé), consulter un avocat
concurrence loyale en complément.

### 10.1 Ce qu'on peut écrire — exemples canoniques validés

- ✅ « Acunetix flague des FP sur CDN par détection HTTP/2 générique »
  (factuel, vérifiable techniquement)
- ✅ « Detectify Pro coûte ~400 €/mois pour Surface Monitoring »
  (factuel, source pricing publique)
- ✅ « Burp Pro est un outil manuel pour pentester » (factuel,
  positionnement public)
- ✅ « Intruder a ~80 modules vs nos 139 » (factuel, comparable)
- ✅ « Pentera fait du BAS, pas du DAST automatisé externe » (factuel,
  positionnement public)

### 10.2 Ce qu'on ne peut PAS écrire — anti-patterns

- ❌ « Acunetix est nul / dépassé / mort » — jugement, pas factuel
- ❌ « Detectify ne sert à rien » — disparagement gratuit
- ❌ « Burp Pro est obsolète » — faux et insultant pour la communauté
- ❌ « Intruder est une arnaque » — diffamation potentielle
- ❌ « N'utilisez surtout pas X » — appel négatif, casse trust
- ❌ « X cache ses faux positifs » — accusation sans preuve

### 10.3 Règles structurantes

1. **Toujours sourcer les faits** (datasheet, pricing public,
   release notes, blog technique du concurrent). Pas de chiffres
   inventés.
2. **Pas d'attaque ad hominem** sur les fondateurs / employés des
   concurrents. Ceux du marché DAST se croisent en conférence.
3. **Pas d'inflation des défauts.** Si Acunetix flague des FP sur
   CDN, c'est un fait technique — pas « Acunetix est plein de FP ».
4. **Reconnaître les forces honnêtement** (cf. § 2.1, § 3.3, § 8). C'est
   ce qui crée la trust — pas le sales blabla.
5. **Citer les sources publiques uniquement.** Jamais de captures
   d'écran de leur dashboard, jamais de leak de leur doc interne,
   jamais de comparaison avec un compte client réel d'eux.
6. **Ton factuel, pas émotionnel.** « Argos est moins cher de 36 % au
   tier Pro Max » ✅. « Argos est BEAUCOUP MIEUX » ❌.
7. **Cf. [`tone_of_voice.md` § 4](tone_of_voice.md#4-vocabulaire-banni)**
   pour les adjectifs marketing bannis (innovant, révolutionnaire,
   leader, premium…) qui s'appliquent aussi à la comm comparative.

### 10.4 Cas limite — anti-disparagement légal

> _§ à compléter en P17 (Conformité) avec un avocat concurrence
> loyale dans la boucle, notamment pour la page Pricing publique
> (`/pricing`) et les blog posts comparatifs indexés. Les règles
> ci-dessus sont safe par défaut mais pas un substitut au conseil
> juridique pour des comparaisons publiques agressives._
