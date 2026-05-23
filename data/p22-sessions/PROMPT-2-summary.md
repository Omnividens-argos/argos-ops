# P22.D — Session 2 (Tech finition + Veille Threat Intel)

**Date** : 2026-05-23
**Branche cible** : `feat/p22d-veille-tech-9-bots` (working tree partagé
avec d'autres sessions parallèles → commits faits sur la branche active
au moment du commit ; le founder consolide).
**Push** : zéro (commits **LOCAUX uniquement**, instruction stricte du prompt).

## Helper factorisé

**`argos_ops/agents/_fetcher_base.py`** — helper httpx commun à tous
les watchers qui appellent du web public. Implémente :

- Cache disque 24 h dans `data/_fetcher_cache/` (clé
  `sha256(method|url|body)`), TTL configurable.
- Retry exponentiel sur `TimeoutException` / `NetworkError` / 5xx
  (max 3 tentatives, backoff `2^attempt * (0.5..1.0)` plafonné 30 s).
- Rate-limit par host (1 s par défaut, process-local).
- User-Agent canonique `Argos-Ops/<service> (+https://omnividens.fr/contact)`
  — on ne se cache pas, les sites peuvent nous bloquer.
- API : `await fetch(url, service=...)` → `FetchResponse`.
- Pas de mock secret : `bypass_cache=True` pour les endpoints volatils
  (ex : CVEMonitor / OSV.dev qui peuvent évoluer dans la journée).

Tests : 11 (`tests/test_fetcher_base.py`).

## Les 9 watchers

### Tech / SRE finition (Sprint 4)

1. **LogAnomalyDetector** (`/run-log-anomalies`, P22.D) — détecte les
   **pics** d'erreurs dans `agent_runs` (fenêtre 1h) vs baseline 24h
   (moyenne horaire). Embed jaune si ratio current/baseline ≥ 3x,
   rouge si ≥ 5x ou ≥ 50/h en absolu. Complémentaire de
   `ErrorTriageBot` (qui clusterise par signature). Tests : 11.

2. **DNSGuard** (cron pur, pas de slash, P22.D) — snapshot DNS A/MX/TXT
   de `omnividens.fr` + `ops.omnividens.fr` via `dnspython`,
   comparaison vs snapshot précédent (rangé dans
   `data/dns_snapshots/<domain>.json`). Rouge si A root ou MX
   changent (signal hijack), jaune sur TXT / sous-domaines (rotation
   DKIM normale). Premier run = baseline silencieuse. Tests : 12.

3. **CIFlakeTracker** (`/run-ci-flakes`, P22.D) — analyse les 50
   derniers workflow runs GitHub Actions via `gh api` (subprocess, pas
   de PAT en clair). Flag les jobs qui échouent ≥ 20% du temps avec
   ≥ 3 occurrences absolues. Tests : 5.

### Veille & Threat Intel (Sprint 6)

4. **CompetitorWatcher** (`/run-competitor-watch`, P22.D) — scrape
   hebdo les pages publiques `/pricing` + `/features` listées dans
   `data/competitors/targets.yaml`. Hash sha256 du texte normalisé
   (script/style strippé, whitespace collapsé) vs snapshot. Embed
   jaune sur diff. Premier consommateur du `_fetcher_base`. Tests : 11.

5. **BreachWatcher** (`/run-breach-watch`, P22.D) — croise les breaches
   publics (flux RSS CERT-FR + API HIBP `/breaches`) avec
   `data/crm/customers.yaml`. Rouge si keywords critiques
   (passwords / credentials / api_keys / ssh) sur un domaine client,
   jaune sinon. Garde-fous éthiques stricts : aucun dump réel,
   métadonnées publiques seulement, résultat reste local. Tests : 10.

6. **RegulatoryWatcher** (`/run-regulatory-watch`, P22.D) — flux RSS UE
   / CNIL / ANSSI filtrés par keywords pertinents (rgpd, ai act, nis2,
   dora, cnil, anssi, transposition…). Dedup via GUIDs persistés dans
   `data/regulatory/seen_guids.json` (rolling window 500). Embed jaune
   sur nouvelle entrée. Configurable via `data/regulatory/sources.yaml`.
   Tests : 9.

7. **CVEMonitor** (`/run-cve-monitor`, P22.D) — distinct du
   `DependencyAuditor` (P22.C qui scanne *notre* stack) : scrute la
   stack **déclarée par les prospects/clients** dans
   `customers.yaml` (champ `stack:`) via OSV.dev batch. Bypass cache
   (CVE volatiles). Réutilise `_map_severity` du DependencyAuditor.
   Embed rouge sur HIGH/CRITICAL. Tests : 7.

8. **DarkWebMonitor** (`/run-dw-monitor`, P22.D, MVP) — interroge la
   liste publique HIBP `/breaches` et croise par `Domain`. MVP sans
   auth domain-search (qui exigerait vérification de propriété). Sell
   point pour outbound : "~X comptes de votre domaine dans le breach
   Y". Aucun email individuel n'est manipulé. Tests : 7.

9. **BountyRadar** (cron pur, pas de slash, P22.D) — agrège les
   programmes publics HackerOne (HTML stub MVP) et YesWeHack (API
   JSON publique) filtrés par keywords sectoriels (saas, fintech,
   infosec…). Dedup via `data/bounty/seen_programs.json`. Tests : 7.

## Stack technique

- Nouvelles deps Python : `dnspython>=2.6`, `feedparser>=6.0`
- Helper `_fetcher_base.py` factorisé (cache + retry + rate-limit + UA)
- Helper `_watcher_base.py` (P22.B) consommé sans surcharge par les 9 bots
- **Total tests P22.D** : **90 verts**
  (11 fetcher + 11 log_anomaly + 12 dns + 11 competitor +
  5 ci_flake + 10 breach + 9 regulatory + 7 cve + 7 dw + 7 bounty)
- `ruff` + `mypy --strict` : clean sur les 10 fichiers livrés

## Source unique d'avancement

- `docs/ARGOS_OPS_PLAN.md` Annexe D : 9 lignes flippées
  `[ ] ⬜` → `[x] ✅` (3 dans §7 Tech/SRE + 6 dans §8 Veille).
- Compteur tête : `33 livrés → 42 livrés` (Python actifs), roadmap
  `43 → 34`.
- `argos_ops/ops_dashboard/frontend/src/lib/agentCatalog.ts` : 9 entrées
  passées de `status: "roadmap"` à `status: "active"` avec ajout du
  `name` canonique (pour que le drawer Admin Panel sache router).

## Commits locaux

- **Commit 1** (`e79bc6e`) — `_fetcher_base` + 3 premiers watchers
  (LogAnomaly + DNSGuard + CompetitorWatcher) + tests + scripts +
  slashes + .gitignore + deps.
- **Commit 2** — 6 watchers restants + tests + scripts + 5 slashes +
  patch Annexe D + agentCatalog.ts + ce résumé.

Aucun `git push`, aucun `gh pr create` lancé.

## Limitations connues

- **DNSGuard** : fallback gracieux si `dnspython` indisponible
  (silence). Vérification SPF/DKIM canonique non implémentée (seul
  l'aller-retour `notAfter` est lu).
- **CIFlakeTracker** : pas de heuristique "fail puis pass sur la même
  SHA" (vraie definition de flake) — utilise le proxy fail-rate. À
  affiner si bruit.
- **BreachWatcher** : extraction du domaine via regex naïve sur title
  + summary. Précision ≈ 80 %, suffit pour shadow mode.
- **DarkWebMonitor MVP** : limité à la liste statique HIBP. Pour le
  vrai domain search (par-compte), il faut activer une clé HIBP et
  prouver la propriété du domaine — hors scope MVP.
- **BountyRadar** : HackerOne SPA non parsable en HTML pur → stub vide
  pour l'instant, on consomme seulement YesWeHack API. Une intégration
  Playwright serait possible mais hors budget time.

Session 2 OK, prêt pour consolidation.
