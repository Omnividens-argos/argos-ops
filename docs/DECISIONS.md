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

## D-017 — Argos Ops 100 % local-first : Claude Code Pro Max + embeddings open-source, zéro API LLM tierce
**Date :** 2026-05-08
**Partie :** P3 (P3-M3, blocage quota Gemini → révision architecturale)
**Décision :** **Tous les agents IA d'Argos Ops** (P4 à P19) tournent
**localement sur l'ordi du fondateur** via Claude Code Pro Max (slash
commands invoqués par cron / Claude Code SDK). **Aucune API LLM tierce**
(Gemini, OpenAI, Voyage, etc.) n'est utilisée par Argos Ops. Les
**embeddings KB / RAG** sont produits par un **modèle open-source local**
(`intfloat/multilingual-e5-base` via `fastembed`, 768 dims natif, exécuté
en CPU sur la machine du fondateur ou sur le serveur SecHunter selon le
composant). **Aucun coût IA récurrent — aucun quota — aucune dépendance
externe.**
**Pourquoi :**
- **Contrainte fondatrice de [`CLAUDE.md`](../CLAUDE.md) Vision** : « 0 €
  de SaaS récurrent en plus de Claude Pro/Max ». Le passage par Gemini
  free tier semblait rentrer dans cette contrainte mais a buté sur le
  quota daily exhausted en P3-M3 (premier seed KB), confirmant que
  « free tier = quota = dépendance externe ». Trade-off rejeté
- **Cohérence avec ce qu'utilise déjà le fondateur** : Claude Code Pro
  Max est le runtime de pensée principal d'Argos Ops dès P4. Pousser
  toutes les capacités IA sur ce même runtime simplifie l'architecture
  (un seul provider, un seul abonnement, un seul billing à surveiller)
- **Souveraineté donnée** : aucun appel LLM ne sort vers un tiers
  pendant le traitement des emails / leads / interactions clients. Pas
  de prompt qui transite chez Google/OpenAI. Cohérent avec la promesse
  RGPD/AI Act du produit et avec la mémoire utilisateur « cibles d'audit
  interne ne doivent pas fuiter en KB »
- **Aucun blocage de quota possible** : un agent local consomme le
  budget de jetons de l'abonnement Claude Pro Max (limites forfaitaires
  connues). Pas de risque de 429 RESOURCE_EXHAUSTED sur du free tier
  partagé avec d'autres usages

**Trade-off accepté explicitement par le fondateur :**
- **L'ordi doit être allumé** pour que les agents tournent. Un email
  arrivé à 3 h du matin attend le réveil du fondateur. Idem pour le
  chat widget visiteurs nocturnes (P8) : réponse différée jusqu'à
  l'allumage de l'ordi. **Acceptable pour un solo-fondateur en early
  stage** ; révision possible quand le CA justifie un Mac mini /
  Raspberry Pi 5 dédié 24/7
- **Latence de réponse chat live** plus élevée qu'un Gemini Flash hot
  (Claude Code lance un nouveau processus à chaque slash command) —
  acceptable pour le volume early stage (≤ 100 chats / jour)

**Implication technique — révision partielle de D-001 :**
- **Composants qui restent sur serveur SecHunter (`204.168.171.71`)** :
  - **Postgres** DB `argos_ops` + extension pgvector → conserve les
    chunks KB, leads, interactions, agent_runs (D-001 valide pour la
    couche données)
  - **Redis** index 3 → cache, quotas, idempotency keys, **queue
    `inbox_pending`** pour les webhooks 24/7 (chat widget P8, push
    Stripe / Gmail)
  - **Webhook receivers HTTP** (chatbot widget endpoint
    `chat.omnividens.fr`, futurs webhooks Stripe / Gmail push / etc.) →
    poussent les événements dans la queue Redis, **pas de réponse
    synchrone**. Survit aux extinctions de l'ordi du fondateur
- **Composants qui migrent sur l'ordi du fondateur** :
  - **Tous les agents IA** (P4 à P19) — slash commands Claude Code
    lancés par **cron sur l'ordi** (Windows Task Scheduler ou cron
    WSL2)
  - **Modèle d'embedding e5-base** (`fastembed` ONNX, ~280 MB poids)
    → embarqué dans le venv Python local. Premier appel télécharge les
    poids, ensuite 0 round-trip réseau
- **Stack mise à jour côté Argos Ops** :

  | Couche | Choix v1 (D-001 / plan initial) | Choix v2 (D-017) |
  |---|---|---|
  | Runtime de pensée | Claude Code Pro/Max via cron | **inchangé** |
  | LLM chat live (P8) | Gemini 1.5 Flash free tier | **Claude Code Pro Max via slash command + queue Redis pour les webhooks 24/7** |
  | Embeddings KB | Gemini `embedding-001` | **`fastembed` + `intfloat/multilingual-e5-base` local (768 dims natif)** |
  | Cron host | utilisateur Linux du serveur SecHunter | **cron / Task Scheduler sur ordi du fondateur** |
  | Webhook endpoint | endpoint FastAPI sur serveur | **inchangé (serveur), mais réponse via queue Redis pull-based depuis l'ordi** |

- **Variables d'environnement à réviser** :
  - `GEMINI_API_KEY` reste dans `.env.example` mais devient
    **optionnel / non-utilisé par Argos Ops** (peut être conservé pour
    le scanner SecHunter qui est un produit séparé, voir « Portée »
    ci-dessous)
  - Pas de nouvelle variable d'env requise pour `fastembed` — modèle
    téléchargé au premier run dans le cache utilisateur
- **Migration `pyproject.toml`** :
  - Ajout : `fastembed>=0.3` (et ses deps ONNX)
  - `google-genai` reste pour le **scanner SecHunter BYOK** (cf.
    portée ci-dessous), mais Argos Ops ne l'appellera plus

**Portée — ce que D-017 ne révoque PAS :**
- **D-011** (Argos scanner BYOK multi-provider IA) reste valide pour le
  **produit Argos / SecHunter** que l'on vend aux clients. Les clients
  du scanner gardent le choix de leur provider IA (Anthropic, OpenAI,
  Google, DeepSeek). D-017 ne s'applique qu'à **Argos Ops** (la flotte
  d'agents internes qui fait tourner l'acquisition / conversion /
  support / admin du SaaS)
- **Les fichiers KB** dans `data/knowledge_base/` restent inchangés —
  ils décrivent le scanner Argos (pour les clients) et les concepts
  métier. Pas de réécriture de la KB nécessaire
- **D-001** (hébergement DB / Redis sur serveur SecHunter) reste
  partiellement valide — la couche données reste sur le serveur. Seuls
  les agents IA (couche calcul) migrent sur l'ordi du fondateur

**Annule / révise :**
- **D-001** (Hébergement mutualisé SecHunter) — **partiellement révisé**
  pour la couche calcul agents IA qui passe local. D-001 reste valide
  pour la couche données + webhook endpoints HTTP
- **`docs/ARGOS_OPS_PLAN.md`** (Partie 1.3 stack technique, Partie 8
  chatbot widget Gemini, Partie 3.3 embeddings Gemini) — réécrit dans
  la même PR P3-M3
- **`docs/ARCHITECTURE.md`** (Sections 2/3/5/6) — réécrit dans la même
  PR P3-M3

**Action de suivi — alignement docs (faite dans la même PR P3-M3) :**
1. ✅ `docs/DECISIONS.md` — D-017 enregistrée (cette entrée)
2. `docs/ARCHITECTURE.md` — section 5 stack v2, section 2 composants
   v2, section 3 flux d'exécution v2, section 6 hébergement nuancé
3. `docs/ARGOS_OPS_PLAN.md` — Partie 1.3 stack figée v2, Partie 8
   chatbot widget Claude Code + queue Redis, Partie 3.3 embeddings
   e5-base local, métriques coût mises à jour
4. `CLAUDE.md` — état d'avancement / Stack notée v2
5. `argos_ops/config.py` — `gemini_api_key` devient optionnel
6. `pyproject.toml` — ajout `fastembed>=0.3`
7. `scripts/seed_kb.py` — refactor `_embed()` pour utiliser
   `fastembed.TextEmbedding('intfloat/multilingual-e5-base')`

**Question ouverte (à trancher en P5+) :**
- **Mac mini / Raspberry Pi 5 dédié 24/7** comme « relai local » qui
  consomme l'abonnement Claude Code Pro Max sans demander à l'ordi de
  développement du fondateur de tourner. À budgéter quand le coût
  d'opportunité (mails ratés, chat widget non répondu la nuit) dépasse
  le coût d'achat (~150-300 €). Pas un blocker pour Sprint 0/1.

---

## D-018 — Stack email pro Argos Ops : OVH Zimbra IMAP/SMTP (pas Gmail Workspace, pas self-host)
**Date :** 2026-05-08
**Partie :** P5 (EmailBot inbound — pré-décision technique)
**Décision :** **EmailBot et tout futur agent qui lit/envoie depuis
`contact@omnividens.fr`** se branchent sur l'**OVH Email Cloud Pro
(Zimbra)** déjà actif via les **protocoles IMAP/SMTP standards**, pas
Gmail API ni self-host. La mention « Gmail API » dans le plan
[`ARGOS_OPS_PLAN.md`](ARGOS_OPS_PLAN.md) Partie 5 est révisée.
**Pourquoi :**
- **OVH Zimbra est déjà actif et payé** (~2-3 €/mois pour 1 boîte). C'est
  du socle business pré-existant, pas un SaaS récurrent ajouté en plus
  → respecte la contrainte fondatrice de [`CLAUDE.md`](../CLAUDE.md)
  Vision (« 0 € de SaaS récurrent en plus de Claude Pro/Max »)
- **Gmail Workspace** demande un abonnement payant (~6,60 €/mois Business
  Starter, ~80 €/an pour 1 boîte). Ajoute un coût récurrent que l'OVH
  existant rend inutile
- **Self-host Mailcow / Zimbra OSE / Postfix** sur le serveur SecHunter
  → 0 € direct mais coût caché énorme : maintenance, surface d'attaque,
  et surtout **délivrabilité catastrophique au launch** (IP fraîche = 4-8
  semaines en spam-trap / blocklists). Pour P13 OutboundBot c'est
  rédhibitoire — un serveur mail self-host frais ruine la réputation IP
  du domaine `omnividens.fr` pendant des mois
- **Cloudflare Email Routing + Gmail perso** → 100 % gratuit pour la
  réception, mais l'envoi demande config DKIM/SPF custom + SMTP
  authentifié tiers (Brevo / Resend / Gmail Send-mail-as) qui ajoute
  une surface d'erreur DNS et une dépendance à un autre SaaS gratuit
  free-tier (qui peut sauter, cf. l'incident Gemini en P3-M3)
- **IMAP + SMTP standards** : Argos Ops EmailBot lira via
  `imap-tools` ou équivalent + enverra via `aiosmtplib`. Code plus
  simple que Gmail API (pas de flow OAuth2 complexe à brancher)

**Implication technique — ce que le code Argos Ops va consommer :**
- **Variables d'env (`.env.local`)** à ajouter en P5 :
  ```
  EMAIL_IMAP_HOST=ssl0.ovh.net    # à confirmer dans le manager OVH
  EMAIL_IMAP_PORT=993
  EMAIL_SMTP_HOST=ssl0.ovh.net
  EMAIL_SMTP_PORT=465
  EMAIL_USER=contact@omnividens.fr
  EMAIL_PASSWORD=...               # password de la boîte OVH
  ```
- **Migration `pyproject.toml`** :
  - Ajout : `imap-tools>=1.5` (lib IMAP simple async-compatible) ou
    `imapclient` (alternative bas niveau)
  - Ajout : `aiosmtplib>=3.0` (SMTP async)
  - `google-api-python-client` ne sera **pas** consommé par Argos Ops
    (peut rester optionnel pour intégrations Gmail tierces si jamais
    nécessaire un jour, mais Argos Ops principal n'en a plus besoin)
- **EmailBot pipeline** (cf. `ARCHITECTURE.md` § 3 flux d'exécution
  révisé) : pull IMAP → classify → CRM upsert → drafter via Claude Code
  Pro Max (D-017) → judge Tier 1 → SMTP send si auto-send

**Trade-off accepté :**
- **Latence IMAP** légèrement plus haute que Gmail API (poll IMAP toutes
  les 15 min vs Gmail watch push). Acceptable pour le volume early
  stage (≤ 50 emails/jour entrants)
- **Pas de threading natif Gmail-style** côté lecture brute. Géré par
  l'agent (groupage par `In-Reply-To` + `References` headers, standard)

**Portée :**
- D-018 ne concerne que la **boîte support entrante**
  `contact@omnividens.fr` lue par EmailBot (P5) et écrite par
  EmailBot / SupportBot (P5/P6)
- **OutboundBot (P13)** utilisera un **domaine secondaire séparé** (ex :
  `try-omnividens.com`) pour préserver la réputation délivrabilité du
  domaine principal — pas couvert par D-018 (cf.
  [`COMPLIANCE.md` § 2](COMPLIANCE.md))

**Annule :**
- Mention « Gmail API + IMAP » dans `ARGOS_OPS_PLAN.md` Partie 5
  → à réviser à l'ouverture de P5 : « **IMAP + SMTP standards via OVH
  Zimbra (D-018)** »
- Les fichiers KB (`argos_features.md`, `faq.md`, etc.) ne sont pas
  concernés — ils parlent du scanner SecHunter pour les clients, pas
  d'Argos Ops

**Action de suivi :**
- À l'ouverture de P5 : ajouter `imap-tools` + `aiosmtplib` à
  `pyproject.toml`, créer `argos_ops/integrations/zimbra.py` (wrapper
  IMAP/SMTP), créer `argos_ops/agents/email_bot.py` (héritant de
  `BaseAgent`, pattern DigestBuilder)
- **D-005** (vérification compte `contact@omnividens.fr` chez OVH)
  reste à faire avant le premier run réel — voir `PROGRESS.md`
  § Sessions transverses
- Mettre à jour `ARGOS_OPS_PLAN.md` Partie 5 lors du démarrage de P5
  (Gmail API → IMAP/SMTP D-018)

---

## D-019 — Abandon définitif du chatbot widget site (P8 cancelled)
**Date :** 2026-05-12
**Partie :** P8 (Chatbot widget site — cancelled)
**Décision :** **Argos Ops n'aura pas de chatbot widget sur `omnividens.fr`.**
La Partie 8 du plan (`ARGOS_OPS_PLAN.md`) est **annulée** et retirée de
l'inventaire actif. Le canal entrant prospects/visiteurs reste **l'email
`contact@omnividens.fr` exclusivement** (EmailBot P5 + SupportBot P6
déjà en prod). Le sous-domaine `chat.omnividens.fr` n'est pas provisionné.

**Pourquoi :**
- **Latence incompatible avec D-017** : la stack 100 % local-first via
  Claude Code Pro Max impose une queue Redis pull-based qui répond en
  différé (≥ 1-5 min en heures ouvrées, plus si l'ordi du fondateur est
  éteint). Un chat widget qui affiche « Argos rédige… » et répond 4 h
  plus tard est pire que pas de chat — il signale aux RSSI un produit
  amateur. L'email asynchrone est lui culturellement attendu en BtoB
  pentest.
- **Surface fonctionnelle déjà couverte** par EmailBot P5 (lecture + tri
  + classification + draft humain-validé via `/check-emails`). Un
  formulaire « contact » HTML simple côté site SecHunter → email →
  EmailBot remplit le même rôle sans dette technique.
- **Coût de maintenance disproportionné** vs valeur attendue early
  stage : FastAPI receiver + Caddy + Redis queue + worker cron + widget
  React + bandeau RGPD/AI Act = ~4-6 h dev × 12 surfaces à maintenir
  (privacy.md, ai-disclosure.md § 4, COMPLIANCE.md § 3.1, etc.). Pour
  un volume early stage estimé ≤ 5 visiteurs/jour qui auraient cliqué.
- **Conformité RGPD/AI Act simplifiée** : retirer le chat widget supprime
  le besoin de bandeau IA + détection mots-clés « humain » + cookie de
  session + retention 1 an des conversations. Reste uniquement
  l'email asynchrone, plus standard juridiquement.
- **Réversibilité préservée** : si un jour le volume site le justifie,
  on rouvrira une nouvelle partie (P20+) avec une stack adaptée
  (probablement un Mac mini / Pi 5 dédié 24/7 hors D-017, ou une
  bascule sur Claude API). Pas d'effort perdu — aucun code fonctionnel
  P8 n'avait été écrit (seul stub `argos_ops/chat_widget/__init__.py`
  retiré dans cette PR).

**Implication technique — ce que cette décision retire :**
- **Sommaire `ARGOS_OPS_PLAN.md`** : Partie 8 retirée de la table, sprint
  1 ne contient plus que P5/P6/P7
- **Inventaire skills `ARGOS_OPS_PLAN.md` § 18.1** : `chat-orchestrator`
  retiré de la liste à créer
- **Stack `ARGOS_OPS_PLAN.md` § 1.1** : ligne « LLM chat live » retirée
  de la table technologique
- **Sous-domaines `CLAUDE.md`** : `chat.omnividens.fr` retiré de la
  table des sous-domaines à brancher
- **`ARCHITECTURE.md`** : flux webhook chat retiré (§ 3.1.2 « Webhook
  24/7 »), Caddy chat.omnividens retiré, table stack mise à jour
- **`AGENTS_PLAYBOOK.md`** : entrée « ChatBot P8 » retirée de la table
  des 12 agents, section dédiée retirée
- **`COMPLIANCE.md`** : § 3.1 « Chatbot widget » retiré
- **`data/legal/privacy.md`** : ligne « Chat widget » retirée du tableau
  des traitements
- **`data/legal/ai-disclosure.md`** : § 4 entier « Chat widget — bandeau
  et stockage » retiré + mentions résiduelles dans § 5.2 (mots-clés
  « humain ») + grille AI Act § 6 mises à jour
- **6 fichiers KB** (`tone_of_voice.md`, `pricing.md`, `faq.md`,
  `competitor_compare.md`, `argos_features.md`, `ICP.md`) : retirer
  toutes les mentions « ChatBot widget » comme consommateur futur.
  Re-seed `seed_kb.py` derrière pour aligner les embeddings.
- **Code stubs** : suppression de `argos_ops/chat_widget/`,
  retrait des mentions ChatBot dans `argos_ops/rag/__init__.py`,
  `argos_ops/notifications/__init__.py`, `pyproject.toml` (commentaire)
- **Schéma DB** : commentaire ligne 49 de `0001_init.sql`
  (`agent_name TEXT — 'EmailBot' | 'ChatBot' | ...`) → retrait
  `'ChatBot'` (cosmétique, pas de migration nécessaire)
- **Mockup `mockup/admin-dashboard.html`** : entrée ChatBot widget
  retirée de la liste d'agents pilotables

**Annule :**
- `ARGOS_OPS_PLAN.md` Partie 8 (entière, lignes 709-787 environ)
- `ARGOS_OPS_PLAN.md` table § 1.1 stack v2 → ligne « LLM chat live »
- `ARGOS_OPS_PLAN.md` § 18.1 → skill `chat-orchestrator`
- `ARGOS_OPS_PLAN.md` § 19.3 → KPI latence p95 ChatBot < 5 s
- `CLAUDE.md` → ligne `chat.omnividens.fr` table sous-domaines
- D-017 → mention « chat widget visiteurs nocturnes (P8) » reste
  historique (D-017 est antérieure, on ne la réécrit pas, on précise
  juste dans D-019 que cet exemple ne sera pas implémenté)

**Action de suivi :**
- Cette PR (`chore/drop-p8-chatbot`) effectue tout le cleanup mécanique
- Une fois mergée : créer un formulaire contact HTML simple côté repo
  SecHunter (`omnividens.fr`) qui mailto `contact@omnividens.fr`. Pas
  de dépendance Argos Ops — c'est juste du frontend SecHunter.
- Sprint 1 est officiellement clos : 3 agents en prod (DigestBuilder,
  EmailBot, SupportBot, FinanceBot). Prochaine partie à arbitrer entre
  P15 (circuit breakers) et P16 phase 1 (Admin Control Panel).

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
