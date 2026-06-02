# INFRA-02 — Umami self-host (analytics.omnividens.fr)

> Runbook **manuel** : déploiement opéré par le fondateur sur le serveur prod
> `204.168.171.71`. Aucun agent ni la CI ne lance Umami. Argos Ops ne fait que
> **lire** l'API (LandingOptimizer). Objectif : analytics web 100 % local,
> gratuit, sans cookie (RGPD-friendly) — conforme [D-017](DECISIONS.md).

## Pourquoi Umami

- **0 €** : self-host Docker, pas de SaaS (vs Plausible Cloud / GA).
- **Sans cookie** : pas de bandeau consentement, conforme RGPD par design.
- **Local-first** : la donnée reste sur le serveur Omnividens, pas de tiers.
- Source de vérité des métriques landing pour **LandingOptimizer** (A/B testing).

## Pièces livrées dans le repo (code-only)

| Fichier | Rôle |
|---------|------|
| [`infra/docker/umami/docker-compose.yml`](../infra/docker/umami/docker-compose.yml) | Stack Umami + Postgres dédié |
| [`infra/docker/umami/.env.example`](../infra/docker/umami/.env.example) | Secrets d'infra du container (gabarit) |
| [`infra/caddy/analytics.Caddyfile`](../infra/caddy/analytics.Caddyfile) | Snippet reverse-proxy + TLS auto |
| [`argos_ops/integrations/umami.py`](../argos_ops/integrations/umami.py) | Client API lecture (login → stats) |
| `UMAMI_*` dans [`config.py`](../argos_ops/config.py) / [`.env.example`](../.env.example) | Identifiants de lecture API |

## Déploiement (à faire une fois, sur le serveur prod)

### 1. Préparer les secrets d'infra

```bash
cd infra/docker/umami
cp .env.example .env
# Générer deux secrets distincts :
openssl rand -base64 24   # -> UMAMI_DB_PASSWORD
openssl rand -base64 32   # -> UMAMI_APP_SECRET
# Renseigner UMAMI_CADDY_NETWORK : le réseau Docker de Caddy
docker inspect sechunter-caddy-1 \
  -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}'
```

Reporter ces valeurs dans `.env` (jamais committé — gitignored).

### 2. Lancer le stack

```bash
docker compose up -d
docker compose logs -f umami   # attendre "Listening on ... 3000"
```

Aucun port n'est publié sur l'hôte : Umami n'est joignable que via Caddy.

### 3. Brancher Caddy

Ajouter le contenu de [`infra/caddy/analytics.Caddyfile`](../infra/caddy/analytics.Caddyfile)
au Caddyfile prod (dans le container `sechunter-caddy-1`), puis recharger :

```bash
docker exec sechunter-caddy-1 caddy reload --config /etc/caddy/Caddyfile
```

Vérifier la résolution DNS de `analytics.omnividens.fr` (A → 204.168.171.71)
**avant** le reload pour que Let's Encrypt délivre le certificat.

### 4. Créer le compte + le site dans Umami

1. Ouvrir `https://analytics.omnividens.fr`.
2. Login initial : `admin` / `umami` → **changer le mot de passe immédiatement**.
3. Settings → Websites → **Add website** : Name = `Omnividens`,
   Domain = `omnividens.fr`.
4. Copier le **Website ID** (UUID) et le **tracking snippet**.
5. Coller le snippet `<script>` dans le `<head>` du site omnividens.fr
   (action site, hors de ce repo).

### 5. Brancher la lecture API côté Argos Ops

Dans le `.env` **applicatif** (racine, pas celui d'`infra/docker/umami`) :

```bash
UMAMI_BASE_URL=https://analytics.omnividens.fr
UMAMI_USERNAME=admin
UMAMI_PASSWORD=<le nouveau mot de passe admin>
UMAMI_WEBSITE_ID=<UUID copié à l'étape 4>
# Optionnel : si tu traques un event de conversion côté site
UMAMI_CONVERSION_EVENT=demande-demo
```

> ⚠️ Renseigner ce `.env` **fichier fermé** (éditeur externe / script), jamais
> collé dans une session Claude Code ouverte — risque de fuite des secrets
> dans le transcript.

### 6. Vérifier le wiring

```bash
uv run python -c "import asyncio; from argos_ops.config import get_settings; \
from argos_ops.integrations.umami import UmamiClient; \
print(asyncio.run(UmamiClient.from_settings(get_settings()).fetch_landing_metrics()))"
```

Doit afficher une liste de `UmamiPageMetric` (vide tant qu'il n'y a pas encore
de trafic collecté). Lancer ensuite `/run-landing-optim` : LandingOptimizer
consomme Umami en priorité et ne retombe sur `data/analytics/landing_perf.yaml`
qu'en shadow (vars absentes) ou si l'instance est indisponible.

## Comportement shadow / fallback

| État | Source des métriques |
|------|----------------------|
| Une des 4 `UMAMI_*` manque | `landing_perf.yaml` (manuel) |
| Umami configuré, instance OK | **API Umami** |
| Umami configuré, instance down / erreur | `landing_perf.yaml` (fallback résilient) |
| Umami OK mais 0 page | `landing_perf.yaml` (fallback) |

## Mapping des métriques

`UmamiPageMetric` est dérivé des totaux Umami **scopés par URL** (`/stats?url=`) :

- `visits` = sessions (fallback pageviews si 0)
- `bounce_rate` = `bounces / visits`
- `avg_time_seconds` = `totaltime / visits`
- `conversions` = compte de l'event `UMAMI_CONVERSION_EVENT` sur la page
  (0 si non configuré → la proposition « CR < 1 % » ne se déclenche pas)

## Maintenance

- **Backups** : le volume `umami-db-data` (Postgres) est couvert par le
  BackupVerifier si on l'ajoute à `data/backup/manifest`. Sinon `pg_dump`
  périodique du container `argos-umami-db`.
- **Mise à jour** : bumper le tag d'image dans le compose
  (`ghcr.io/umami-software/umami:postgresql-vX.Y.Z`), `docker compose pull`
  puis `up -d` (migrations DB automatiques au démarrage).
- **Rotation `UMAMI_APP_SECRET`** : invalide les sessions admin en cours
  (re-login requis), sans impact sur la donnée.
