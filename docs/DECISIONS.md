# Argos Ops — Journal des décisions

> Ce fichier consigne **toutes** les décisions structurantes prises pendant la mise en
> place et l'évolution d'Argos Ops. Chaque entrée est datée et explique pourquoi la
> décision a été prise. Les décisions ne sont jamais effacées — si une décision est
> annulée plus tard, on ajoute une nouvelle entrée qui la révoque, en référençant
> l'entrée annulée.

---

## D-001 — Hébergement mutualisé avec SecHunter
**Date :** 2026-05-07
**Partie :** P0.4 (Vision et décisions préalables)
**Décision :** Argos Ops tourne sur le même serveur que SecHunter (`204.168.171.71`),
pas sur un VPS dédié.
**Pourquoi :** zéro coût supplémentaire, Caddy déjà en place pour ajouter
`ops.omnividens.fr` et `chat.omnividens.fr`, Postgres + Redis déjà actifs.
**Risque accepté :** un crash serveur impacte les deux services en même temps. Non
bloquant en early stage. On migrera vers un VPS dédié si Argos Ops devient critique
au CA.

---

## D-002 — PostgreSQL : nouvelle DB `argos_ops` sur le cluster existant
**Date :** 2026-05-07
**Partie :** P0.4
**Décision :** créer une nouvelle base `argos_ops` sur le cluster Postgres existant
(`sechunter-postgres-1`), avec un user dédié `argos_ops`. Pas de partage de schéma
avec la DB SecHunter.
**Pourquoi :** zéro coût, isolation logique propre, backups indépendants via
`pg_dump argos_ops`. Les éventuelles données nécessaires (clients, MRR Stripe, etc.)
seront répliquées par les agents via API Stripe en source de vérité.
**Implication technique :** `CREATE DATABASE argos_ops OWNER argos_ops` + extension
pgvector activée dans cette DB (`CREATE EXTENSION vector`). Index Redis 3 réservé
(`REDIS_URL=redis://localhost:6379/3`), SecHunter utilise déjà 0-2.

---

## D-003 — Sprint prioritaire : Sprint 1 (inbound + finance)
**Date :** 2026-05-07
**Partie :** P0.4
**Décision :** démarrer par Sprint 1 (EmailBot, SupportBot, FinanceBot, ChatBot
widget) avant Sprint 2 (content + SEO + connecteurs sociaux).
**Pourquoi :**
- Gain de temps dès J+7 sur les emails / tickets / facturation
- La KB construite pour SupportBot sert directement à ContentBot/SEOBot du Sprint 2
- Risque visibilité minimal (back-office privé), permet de valider la mécanique
  avant d'exposer en public

---

## D-004 — Remplacement X (Twitter) par Mastodon dans la stratégie sociale
**Date :** 2026-05-07
**Partie :** P1 (P1.D)
**Décision :** retirer X du périmètre Argos Ops, le remplacer par Mastodon
(`infosec.exchange`).
**Pourquoi :** X a supprimé son free tier API en 2026 et bascule en pay-per-use sur
toute action (post, recherche). Casse la contrainte stratégique « 0 € de SaaS
récurrent en plus de Claude Pro/Max » du plan P0. Mastodon offre :
- API ouverte gratuite forever
- Communauté infosec active concentrée sur `infosec.exchange`
- Conformité éthique (federated, no algorithmic feed)
**Implication technique :**
- Stack mise à jour : `Mastodon.py` au lieu de `tweepy`
- Variable d'env : `MASTODON_INSTANCE_URL` + `MASTODON_ACCESS_TOKEN`
- ContentBot (P9) utilisera 4 canaux : LinkedIn / Mastodon / Reddit / Bluesky-future
**Annule :** ligne X / `tweepy` du plan P1.2 / P1.3 / P11.

---

## D-005 — Skip Reddit en P1 (compte trop neuf)
**Date :** 2026-05-07
**Partie :** P1 (P1.C)
**Décision :** ne pas créer l'app Reddit en P1, repousser avant P11 (Sprint 2).
**Pourquoi :** Reddit refuse la création d'app API sur les comptes neufs depuis 2023
(« Responsible Builder Policy »). Le compte du fondateur étant tout neuf, le seuil
non documenté (~30 jours + karma) n'est pas atteint.
**Action de suivi :** todo `P11-PREP` — recréer l'app Reddit avant le démarrage de P11.

---

## D-006 — 2 apps LinkedIn Developer au lieu d'une seule
**Date :** 2026-05-07
**Partie :** P1 (P1.E)
**Décision :** créer **deux** apps LinkedIn distinctes :
1. **App #1 « Argos Ops »** — Sign In with LinkedIn + Share on LinkedIn
   (poster sur le profil personnel du fondateur)
2. **App #2 « Argos Ops Page »** — Community Management API
   (poster sur la Page Omnividens id `116001097`)
**Pourquoi :** LinkedIn impose depuis fin 2024 que Community Management API soit
le **seul** product sur l'app pour des raisons de sécurité/conformité. Mêler les
deux usages dans une seule app était impossible. Deux apps = deux sets de credentials
mais permet de garder les deux fonctionnalités.
**Status Community Management API :** soumis le 2026-05-07, en attente d'approbation
LinkedIn (délai 3-7 jours ouvrés).
**Action de suivi :** todo `P1.E-FOLLOWUP` — vérifier l'email LinkedIn dans 3-7 jours.

---

## D-007 — Skip analytics (Plausible / Umami) en P1
**Date :** 2026-05-07
**Partie :** P1 (P1.F)
**Décision :** ne pas installer de système d'analytics web en P1. Repousser
l'installation à une session DevOps dédiée (`INFRA-02`) avant P10 (SEOBot) ou
P12 (AdBot).
**Pourquoi :**
- Pas critique pour Sprint 1 : les KPIs Sprint 1 sont MRR (Stripe), leads (CRM
  Argos), emails inbound (Gmail) — aucun ne dépend d'analytics web
- Plausible Community Edition est lourd (ClickHouse) et le serveur prod est tendu
  (15 G disque libre / 234 M RAM libre / 0 swap)
- Choix futur figé : **Umami self-host** au lieu de Plausible — ~80 MB RAM, peut
  réutiliser le PostgreSQL existant via une DB dédiée `umami`, tient la contrainte
  0 € forever
**Action de suivi :** todo `INFRA-02` — installer Umami self-host avant P10/P12.

---

## D-008 — Migration du plan stratégique et du master prompt vers le repo argos-ops
**Date :** 2026-05-07
**Partie :** P2 (clôture)
**Décision :** déplacer `docs/ARGOS_OPS_PLAN.md` et `docs/ARGOS_OPS_MASTER_PROMPT.md`
depuis le repo SecHunter (`~/Desktop/the good guy/docs/`) vers le repo argos-ops
(`~/Desktop/argos-ops/docs/`). Renommer `ARGOS_OPS_MASTER_PROMPT.md` → `MASTER_PROMPT.md`
au passage pour la concision.
**Pourquoi :** rendre le repo `argos-ops` **autonome**. Bénéfices :
- Sessions Claude Code depuis `~/Desktop/argos-ops/` ont tout le contexte sous la main
  sans devoir lire `../the good guy/docs/` (chemin fragile)
- Si le dossier `the good guy` est déplacé / renommé, rien ne casse côté Argos Ops
- Un VA Tier 3 (futur, P0 §0.3) qui clone `argos-ops` a tout le matériel sans accès
  privilégié au repo SecHunter
- Le plan évolue pendant la mise en place : plus naturel de le faire évoluer dans le
  repo où on bosse activement
- Cohérent avec D-001 qui prévoit qu'Argos Ops puisse migrer vers un VPS dédié si
  critique au CA
**Implication technique :**
- Tous les chemins relatifs `../the good guy/docs/...` mis à jour vers `docs/...` dans
  `CLAUDE.md`, `README.md`, `docs/ARCHITECTURE.md`, `docs/PROGRESS.md`, `docs/MASTER_PROMPT.md`
- Les originaux supprimés du repo SecHunter dans une PR séparée
- `ARGOS_MODULE_BUGS.md` reste dans SecHunter (c'est les bugs des modules de scan,
  pas un artefact Argos Ops)
**Conséquence opérationnelle :** dès P3, toutes les sessions Claude Code Argos Ops se
font depuis `~/Desktop/argos-ops/`. Auto-mémoire Claude associée au path : un nouveau
profil sera créé pour `c--Users-pauzzle-Desktop-argos-ops` (les 3 entrées du profil
SecHunter — profil utilisateur, complétude module, cadence — devront être recopiées
ou recréées dans le nouveau profil au gré des conversations).

---

## D-009 — Postgres en local Docker pour P3, DB serveur reportée à P4/P5
**Date :** 2026-05-07
**Partie :** P3 (P3-M1)
**Décision :** la DB `argos_ops` est d'abord montée en **local** dans un container
Docker (Postgres + pgvector). Le setup serveur (`204.168.171.71`,
container `sechunter-postgres-1`) n'est PAS effectué en P3. Il sera fait au moment
où le **premier agent doit tourner en cron sur le serveur** — typiquement début P4
(`/morning-digest`) ou P5 (EmailBot consommant un IMAP en continu).
**Pourquoi :**
- En P3 on a besoin de la DB pour deux choses seulement : appliquer la migration
  et seeder la KB. Aucun agent ne tourne encore en prod, donc aucun bénéfice à
  héberger la donnée sur le serveur tout de suite.
- Itération rapide : pas de SSH à chaque test, drop/recréation possible en
  secondes pendant qu'on tâtonne sur `seed_kb.py` et la KB.
- Risque évité : zéro chance de toucher à la DB SecHunter prod par accident
  pendant l'apprentissage.
- Parité prod préservée : la migration `0001_init.sql` est idempotente et
  identique local/serveur — au moment de basculer, on rejoue la même migration
  côté serveur en 15 min.
**Implication technique :**
- Docker container `argos-postgres-local` basé sur l'image `pgvector/pgvector:pg16`
  (Postgres + pgvector préinstallé), exposé sur `localhost:5432` (ou autre port
  si conflit avec un Postgres déjà installé localement)
- `DATABASE_URL` dans `.env.local` pointe vers `localhost`
- Au passage prod (P4/P5) : nouvelle entrée `DATABASE_URL_PROD` ou bascule
  via variable d'env, pas de divergence de schéma
**Annule :** rien. Complète D-002 qui reste valable pour la prod.
**Action de suivi :** todo `P4-M1` ou `P5-M1` — créer la DB `argos_ops` sur le
cluster serveur au moment de déployer le premier agent en cron prod.

---

## D-010 — Add-on « scans hors quota » réservé au tier Free
**Date :** 2026-05-08
**Partie :** P3 (P3-M2, flag A `pricing.md`)
**Décision :** l'add-on **Scans hors quota** (19 €/scan) reste **Free-only**.
Pas d'extension aux tiers payants Pro / Team / Pro Max. Un user Pro ou Team
qui défonce son quota est rate-limité jusqu'à minuit J+1 et l'UI lui propose
explicitement l'**upgrade au tier supérieur**, pas l'achat d'un scan à
l'unité. Pro Max est illimité par design.
**Pourquoi :**
- Pro 70 scans/j = 2 100/mois ; Team 250/j = 7 500/mois. À ces volumes, un
  besoin régulier de hors-quota = signal d'upgrade au tier supérieur, pas
  un besoin de metered billing
- Vendre du hors-quota aux tiers payants brouille le signal d'upgrade —
  or le signal d'upgrade Pro→Team→Pro Max est le moteur principal de la
  conversion
- Le hors-quota Free reste un mini-add-on de transition Free→Pro : un user
  Free qui veut un 11ᵉ scan ce jour-ci paie 19 €, ressent la friction,
  comprend qu'à 39 €/mois il a 70 scans/jour
**Implication technique :**
- `core/quota.py` : pas de nouvelle option d'achat hors-quota pour les tiers
  payants. Comportement existant inchangé (rate-limit jusqu'à minuit J+1)
- UI à coder en session ultérieure (P16 ou plus tôt) : message dédié quand
  un Pro/Team hit son quota → CTA upgrade tier supérieur, pas hors-quota.
  Message canonique : « Tu as atteint 70 scans/jour. Upgrade à Team pour
  250 scans/jour, ou attends 24 h. »
- KB `pricing.md` § 6 mise à jour : retirer la mention « (à valider) » et
  acter le garde-fou UX
**Annule :** rien.

---

## D-011 — IA fallback auto Pro Max : BYOK seul, pas de clé serveur Argos
**Date :** 2026-05-08
**Partie :** P3 (P3-M2, flag B `pricing.md`)
**Décision :** la fonctionnalité **IA fallback auto** (Pro Max) bascule
automatiquement entre les **clés API que l'utilisateur a configurées** dans
Settings (≥ 2 providers, ex : Anthropic + OpenAI). **Aucune clé serveur
Argos en backup.** Si tous les providers configurés échouent, le scan
continue en mode dégradé (findings sans corrélation IA / chaînes d'attaque)
et aucun appel sortant ne part vers une clé Argos.
**Pourquoi :**
- Préserve la promesse marketing « 0 € de SaaS récurrent en plus » qui est
  l'argument différenciateur fort pour fintech / santé / défense (Sarah
  cœur ICP). Une clé serveur dilue cette promesse
- Coût LLM côté Argos imprévisible : un Marc qui run en CI peut exploser
  un plafond de 100 calls/mois en 1 journée → soit on bloque (mauvaise
  UX), soit on absorbe (mauvaise marge)
- Plus simple à expliquer dans la KB : « le fallback bascule entre tes
  providers configurés, à toi de configurer au moins 2 clés »
**Implication technique :**
- Le code provider routing doit lister les clés configurées par le user
  Pro Max et basculer sur 429 / 503. Aucun secret Argos serveur dans le
  pipeline d'appel
- KB `pricing.md` ligne tableau « IA fallback auto **(sans BYOK)** » →
  corriger en « **(entre BYOK configurés)** ». La promesse change : ce
  n'est pas « pas besoin de BYOK » mais « fallback automatique entre tes
  BYOK ». Seul tier à avoir le fallback = Pro Max
- UI Pro Max onglet « IA » : message canonique « IA fallback auto activé.
  Bascule automatique entre tes providers configurés en cas de
  rate-limit ou d'erreur. Configure au moins 2 providers (Anthropic +
  OpenAI recommandés) pour que ça soit utile. »
- SupportBot canonical : si un user Pro Max ping « j'ai qu'une clé
  Anthropic, le fallback marche pas » → réponse cadrée « Le fallback
  nécessite ≥ 2 providers configurés. Ajoute une clé OpenAI ou Google
  dans Settings → IA, et il prendra le relais automatiquement. »
**Annule :** la formulation « Pro Max sans clé BYOK personnelle → Argos
utilise sa propre clé Claude (coût absorbé dans le 249 €/mois, plafonné
côté serveur) » dans `data/knowledge_base/pricing.md` § 10 glossaire (ligne
295). Cette formulation était une hypothèse de travail non validée.

---

## D-012 — Définitions canoniques `Watch` et `Chaînes d'attaque` (KB)
**Date :** 2026-05-08
**Partie :** P3 (P3-M2, flag C `pricing.md`)
**Décision :** définitions canoniques figées pour la KB. À utiliser sans
reformulation par SupportBot, ChatBot, OutboundBot et toute doc publique.

**Watch (surveillance continue) — Pro Max uniquement.**
Re-scan automatique programmé d'une cible à intervalle configurable (6 h /
24 h / hebdo) avec alerte sur les changements : nouveau finding ≥ sévérité
minimale, finding RESOLVED qui réapparaît (régression), score de risque
global qui se dégrade. Canaux : Slack webhook, email, push dashboard.
Historique conservé en timeline (`/watch/<target>/timeline`).
- **Cas d'usage type :** Sarah Head of Sec qui gère 15 services en prod et
  veut être prévenue dès qu'un service prend une nouvelle vuln CRITICAL
- **Pourquoi Pro Max only :** consomme des ressources serveur (scans en
  background, scheduler, queues ARQ) non absorbables sur Pro 39 €. Le cas
  d'usage = équipe sécu qui veut du monitoring continu = profil Sarah

**Chaînes d'attaque (attack chains) — Pro / Team / Pro Max.**
À la fin de chaque scan, l'agent IA reçoit la liste complète des findings
et identifie les **séquences exploitables ensemble** au-delà des CVSS
individuels. Chaque chaîne a : un score de criticité (souvent ≥ max des
findings individuels), un PoC step-by-step reproductible, la liste des
findings constitutifs linkés, une remédiation pointant le maillon faible
(souvent le plus simple à corriger casse toute la chaîne). Affichées dans
le rapport sous une section dédiée, prioritaire visuellement.
- **Exemples canoniques :** S3 public + clé AWS leak + IAM permissif =
  « RCE via S3 → escalation cloud → full account » ; cookie sans HttpOnly
  + XSS reflected + pas de CSP = « session hijacking → account takeover »
- **Cas d'usage type :** Marc CTO scaleup qui voit 50 findings et veut
  prioriser les 3 vraiment exploitables ensemble, pas les 47 isolés
- **Pourquoi Pro et plus, pas Free :** nécessite l'agent IA en mode
  corrélation (coûte des tokens chez le provider du user — BYOK). Free
  garde les findings unitaires mais pas la corrélation IA = différence
  concrète qui justifie l'upgrade Pro

**Différence Watch vs Chaînes d'attaque (à clarifier pour SupportBot,
souvent confondus) :**

| | Chaînes d'attaque | Watch |
|---|---|---|
| Quand | Pendant chaque scan (à la fin) | Entre les scans (re-scan auto) |
| Quoi | Corréler les findings d'un seul scan | Comparer les findings sur plusieurs scans dans le temps |
| Tier | Pro / Team / Pro Max | Pro Max uniquement |
| Sortie | Section dans le rapport courant | Timeline + alertes Slack/email |

**Pourquoi figer ça ici :** ces deux termes sont confondus en interne et
seront re-cités dans `argos_features.md`, `competitor_compare.md`, `faq.md`,
le chat widget, les emails OutboundBot et la page Pricing. Une dérive de
formulation entre les surfaces casse la confiance.

**Implication technique :**
- KB `pricing.md` § 10 glossaire mis à jour avec ces définitions
  canoniques (sans le marqueur « à valider »)
- `argos_features.md` (fichier suivant P3-M2) reprendra ces définitions in
  extenso pour la section « Modules avancés » et « Surveillance continue »
- Tableau différence à inclure dans `faq.md` (Q : « C'est quoi la
  différence entre Watch et Chaînes d'attaque ? »)

**Annule :** les définitions « (à valider) » de la table glossaire de
`data/knowledge_base/pricing.md` § 10 (lignes 293-295).

---

## D-013 — Strategist : framing « informatif/audit » en KB publique, fusion intel+LLM en roadmap technique
**Date :** 2026-05-08
**Partie :** P3 (P3-M2, rédaction `argos_features.md` § 4.2)
**Décision :** la KB publique présente le **Strategist** comme une couche
qui « analyse WAF/CMS/stack et génère une stratégie d'attaque
contextualisée intégrée au rapport final pour donner au RSSI la lecture
experte de la cible » — formulation **informative/audit**, pas
prescriptive. Une note implémentation discrète mentionne que la fusion
programmatique entre la stratégie LLM et le pipeline de filtrage modules
est sur la roadmap technique. **Pas de framing « notre IA pilote
l'exécution »** tant que cette fusion n'est pas codée, sous peine d'être
contredit par le code source pour un client technique qui creuserait.
**Pourquoi :**
- Constat de réalité : aujourd'hui, `orchestrator.py:499` ne sauvegarde
  que `strategy.get("notes", "")` ; le filtrage temps-réel des modules
  est fait par `_filter_modules_by_intel()` (orchestrator.py:538-583)
  qui consomme l'intel Phase 0 brute (ports/CMS), pas le JSON LLM
  (`modules_priority`, `excluded_vectors`, `waf_bypass_strategy`)
- Le Strategist produit donc aujourd'hui un riche JSON dont seule la
  clé `notes` (texte libre) atterrit dans le rapport. C'est de l'audit
  pour le RSSI, pas de la prescription pour l'exécution
- Trois options écartées : (A) honnêteté brutale « notre IA est juste
  affichage » → sonne faux et démolit la valeur perçue ; (B)
  marketing-safe « lecture experte de la cible intégrée au rapport » →
  retenu ; (C) survendre comme « pilote l'exécution » → mensonge par
  rapport au code, risque de retour de bâton sur une démo technique
**Implication technique :**
- Texte canonique KB § 4.2 (à coller verbatim dans toute comm publique) :
  « L'agent **Strategist** analyse WAF/CMS/stack et génère une stratégie
  d'attaque contextualisée intégrée au rapport final pour donner au RSSI
  la lecture experte de la cible. »
- Texte canonique pour réponse SupportBot quand un techie demande « est-ce
  que la stratégie LLM filtre vraiment les modules en temps réel ? » :
  « Aujourd'hui le filtrage temps-réel est piloté par l'intel Phase 0
  (ports/CMS détectés) qui exclut déjà ~90 % des vecteurs impossibles
  avant le scan. La stratégie LLM enrichit le rapport pour audit. La
  fusion programmatique des deux est sur notre roadmap technique. »
- **Action de suivi (côté SecHunter, à créer par le fondateur quand il
  veut)** : ticket `feat/strategist-prescriptive-routing` — brancher
  `modules_priority` + `excluded_vectors` du JSON Strategist dans
  `_filter_modules_by_intel()`. Estimation : ~30 LOC + tests. Une fois
  livré, mettre à jour D-013 (révoquer ou passer en framing
  prescriptif) + KB § 4.2.
**Annule :** rien.

---

## D-014 — Compliance mapping : sortie factuelle (count par exigence), pas de score % marketing
**Date :** 2026-05-08
**Partie :** P3 (P3-M2, rédaction `argos_features.md` § 4.6)
**Décision :** la KB publique annonce le compliance mapping comme **un
mapping exhaustif des findings vers les exigences violées, avec un count
de findings par exigence**. **Pas de score % de couverture compliance**
type « 78 % PCI-DSS compliant ». L'argument vendeur est explicitement
« pas de score marketing creux, on vous donne la matière brute pour votre
rapport d'audit ».
**Pourquoi :**
- État du code (`core/compliance_mapper.py:14, 246-389`) : la sortie est
  une dict `{framework: {requirement: {name, count, findings: [...]}}}`.
  Aucun calcul de pourcentage n'existe — ce serait à inventer
- Un score % « 78 % PCI-DSS » est arbitraire (sur quoi est calculée la
  base ? les 12 requirements PCI-DSS ? les 250+ sous-contrôles ? le
  périmètre scope du scan ?) et un auditeur exigera de le justifier
  ligne par ligne en review
- Format factuel = utilisable directement dans le rapport d'audit que
  prépare le RSSI/DPO. « 5 findings violent l'exigence PCI-DSS 6.2.4 »
  est actionnable. « Vous êtes à 78 % » ne l'est pas
- Versions confirmées : **OWASP Top 10 2021** (clés `A01:2021` à
  `A10:2021`), **PCI-DSS 4.0** (refs 1.2.1, 2.2.1, 3.4.1, 4.2.1, 6.2.4,
  7.2.2, 8.3.1, 10.2.1, 10.3.1, 11.3.1), **RGPD** (5 articles : 5(1)(f),
  25, 32 majoritaire, 33, 34)
**Implication technique :**
- Texte canonique KB § 4.6 (à coller verbatim) : « Triple mapping
  framework : OWASP Top 10 2021, PCI-DSS 4.0, RGPD (Art. 5(1)(f), 25, 32,
  33, 34). Sortie factuelle : count de findings par exigence violée, pas
  de score % de couverture. Utilisable directement dans le rapport
  d'audit. »
- Texte canonique pour cold call quand un prospect demande « est-ce que
  vous certifiez la compliance ? » : « Argos n'est pas un certificateur.
  On vous fournit le mapping factuel `finding → exigence violée` que
  votre auditeur exigerait de toute façon. C'est plus rapide à
  contester ou à patcher que les rapports compliance % de nos
  concurrents. »
**Annule :** rien.

---

## D-015 — Faux positifs : framing tactique « 3 niveaux + boucle support », marquage user en roadmap
**Date :** 2026-05-08
**Partie :** P3 (P3-M2, rédaction `faq.md` § « Faux positifs »)
**Décision :** la KB publique annonce **3 niveaux de filtrage FP** côté
Argos (calibration oracles, Q1-Q5 hardening anti-bot, agent Analyst IA
qui score `confidence_score < 0.5 → FP exclu`). Si un FP survit aux 3
niveaux, l'utilisateur **ouvre un ticket support → un humain Argos
analyse → fix livré dans le batch v2 suivant**. Le **bouton « Marquer
FP » en libre-service côté user est positionné comme roadmap** (« Pro+
T3 2026 »), pas comme feature livrée.
**Pourquoi :**
- État du code (vérifié 2026-05-08) : le modèle `Finding` a bien
  `false_positive: bool` + `fp_reason: str` + `confidence_score: float`
  (`models.py:147-151`), et l'agent Analyst exclut auto les findings
  `confidence < 0.5` (`scans.py:251-253`) — la logique côté serveur
  existe déjà et fonctionne
- Manquent côté UX : aucun bouton « Mark as FP » dans le dashboard
  React, aucun endpoint `PATCH /api/findings/{id}`, aucun mécanisme
  par cible+module pour empêcher la réémission au prochain scan
- Trois options examinées : (A) framing honnête tactique « auto-filtre
  IA + boucle humaine » → retenu, crédible parce que 66 bugs FP
  documentés en post-v2 ; (B) framing roadmap honnête « libre-service
  arrive » → mentionné en complément ; (C) build immédiat (~150-200
  LOC + UI) → pas dans le scope P3-M2, repoussé
- Le « 0 faux positif » de la phrase clinchante crée une attente d'**outillage proactif**.
  Le framing (A) tient cette promesse en disant « notre IA fait le tri,
  un humain corrige les ratés », sans inventer de feature inexistante
**Implication technique :**
- Texte canonique KB `faq.md` (à coller verbatim) : « Argos applique
  3 niveaux de filtrage FP : (1) calibration des oracles au code
  (66 bugs FP corrigés en post-v2), (2) Q1-Q5 hardening anti-bot/SPA
  /WordPress sur chaque module, (3) agent Analyst IA qui score chaque
  finding (`confidence_score` 0-1) et exclut ceux < 0.5. Si malgré ces
  3 niveaux un FP passe : `support@omnividens.fr` → humain analyse →
  fix dans le batch v2 suivant. Le marquage en libre-service côté user
  arrive sur la roadmap Pro+ T3 2026. »
- **Action de suivi (côté SecHunter)** : tickets à créer quand le
  fondateur veut activer la roadmap :
  1. `feat/finding-mark-fp` — endpoint `PATCH /api/findings/{id}` +
     bouton dashboard + persistance par `(target, module)` (~150-200 LOC)
  2. Bonus argument vente : « FP-mark explicable et traçable » vs
     Acunetix qui a un FP-mark mais opaque
**Annule :** rien.

---

## D-016 — Rétention findings : promesse minimale tenue, purge automatique en roadmap
**Date :** 2026-05-08
**Partie :** P3 (P3-M2, rédaction `faq.md` § « Sécurité & confidentialité »)
**Décision :** la promesse de [`pricing.md`](../data/knowledge_base/pricing.md)
(« Free 30 j / Pro 90 j / Team 1 an / Pro Max illimité ») est tenue
**comme rétention minimale garantie**, pas comme purge automatique. En
pratique aujourd'hui, les findings sont conservés **au-delà** de cette
durée tant que le job cron de purge n'est pas implémenté. L'utilisateur
qui veut purger immédiatement utilise `Account → Delete scan` (route
`DELETE /api/scans/{id}` existante) ou `Account → Delete data` pour
suppression complète. **Pas de modification de `pricing.md` au launch**
— la promesse minimale reste valide.
**Pourquoi :**
- État du code (vérifié 2026-05-08) : le modèle `Scan` a bien les
  champs `deleted_at` et `archived_at` (`models.py:240-241`) mais
  aucun cron de purge automatique selon le tier n'existe — la promesse
  pricing est de la rétention **minimale**, pas un upper bound de
  conservation
- Trois options examinées : (A) implémenter le cron de purge (~50 LOC
  dans `core/database.py`) → pas dans le scope P3-M2, repoussé ; (B)
  reformuler pricing.md « pas de purge auto, suppression manuelle » →
  rejeté car fragilise la promesse contractuelle ; (C) tenir la
  promesse comme rétention minimale (sur-livré accepté) avec mention
  honnête en faq.md → **retenu**
- Du point de vue user : conserver les findings plus longtemps que la
  promesse n'est pas un préjudice — c'est de la donnée propriétaire
  qu'il peut consulter. Le seul cas où ça pose problème est RGPD droit
  à l'oubli — couvert par `Account → Delete data`
- Position cohérente avec D-015 (FP marking) : on assume une roadmap
  technique honnête côté KB plutôt que d'inventer des features
**Implication technique :**
- Texte canonique KB `faq.md` (à coller verbatim) : « Rétention minimale
  garantie par tier : Free 30 j, Pro 90 j, Team 1 an, Pro Max illimité.
  En pratique aujourd'hui, les findings sont conservés au-delà de cette
  durée minimale — la purge automatique en cron est sur la roadmap
  technique. Pour purger immédiatement, `Account → Delete scan` (par
  scan) ou `Account → Delete data` (suppression complète RGPD). »
- **Action de suivi (côté SecHunter)** : ticket
  `feat/findings-retention-cron` — job cron qui purge les findings au-delà
  du seuil de rétention selon le tier user (~50 LOC + tests). À créer
  quand le fondateur veut activer.
**Annule :** rien.

---

## Modèle pour les futures décisions

```markdown
## D-XXX — Titre court de la décision
**Date :** YYYY-MM-DD
**Partie :** PX (référence dans le plan)
**Décision :** ce qui a été tranché en 1-2 phrases
**Pourquoi :** raison principale + alternatives écartées
**Implication technique :** (optionnel) ce que ça change concrètement dans le code/infra
**Annule :** (optionnel) référence aux entrées D-XXX précédentes que ça invalide
**Action de suivi :** (optionnel) todos générées
```
