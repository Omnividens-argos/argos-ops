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
