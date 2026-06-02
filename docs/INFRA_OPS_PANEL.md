# P16.B/D — Durcissement de l'Admin Control Panel (ops.omnividens.fr)

> Runbook **manuel** : configuration opérée par le fondateur. Le panel est le
> cockpit privé qui pilote toute la flotte (run-now, reset breakers, config) —
> il ne doit JAMAIS être exposé en clair.

## Modèle de menace & couches

Defense-in-depth à **deux niveaux**. L'un ne remplace pas l'autre.

| Couche | Où | Rôle |
|--------|-----|------|
| **Caddy** (1ʳᵉ ligne) | [`infra/caddy/ops.Caddyfile`](../infra/caddy/ops.Caddyfile) | TLS, filtrage IP sur la **vraie IP client**, Basic auth |
| **Applicatif** (defense-in-depth) | [`auth.py`](../argos_ops/ops_dashboard/auth.py) | Basic + JWT + TOTP 2FA + allowlist sur le peer TCP |

⚠️ **Pourquoi deux filtrages IP ?** Derrière Caddy, l'app ne voit que l'IP du
conteneur Caddy (le « peer »), pas le visiteur. Le filtrage IP fiable est donc
celui de **Caddy** (`remote_ip`). L'allowlist applicative (`OPS_DASHBOARD_IP_ALLOWLIST`)
est un **garde-fou** qui ne sert que si l'app est exposée *sans* Caddy (mauvaise
conf) — dans ce cas le peer EST le visiteur.

## Principe : fail-open

Tant qu'aucune variable `OPS_DASHBOARD_*` n'est renseignée, l'auth applicative
est **désarmée** (le panel reste ouvert en local, les tests passent). Elle
s'active dès que `OPS_DASHBOARD_BASIC_AUTH_USER` **et** `_PASSWORD` sont posés.

## Variables (`.env` applicatif)

| Variable | Effet |
|----------|-------|
| `OPS_DASHBOARD_BASIC_AUTH_USER` / `_PASSWORD` | Arme le Basic auth (constant-time) |
| `OPS_DASHBOARD_JWT_SECRET` | Signe les JWT de session (HS256). Requis pour `/api/auth/login` |
| `OPS_DASHBOARD_IP_ALLOWLIST` | CIDR/IP séparés par virgules, sur le peer. Vide = pas de filtrage app |
| `OPS_DASHBOARD_TOTP_SECRET` | Active la 2FA TOTP (base32). Quand présent, **le Basic seul ne suffit plus** |

Générer les secrets (fichier **fermé**, jamais collé dans une session Claude) :

```bash
openssl rand -hex 32          # -> OPS_DASHBOARD_JWT_SECRET
python -c "import pyotp; print(pyotp.random_base32())"   # -> OPS_DASHBOARD_TOTP_SECRET
```

## Endpoints & comportement du middleware

- **Exemptés** (jamais protégés) : `/api/health` (monitoring), `/api/stripe/webhook`
  (auth = signature HMAC), `/api/auth/login`.
- **IP allowlist** : évaluée en premier, sur **toutes** les routes (même health).
  Si elle est active et que le peer n'est pas dedans → `403`.
- **Auth** : sur les routes non exemptées, il faut soit un **Basic** valide
  (si TOTP désarmé), soit un **`Authorization: Bearer <jwt>`** valide.

### Flux 2FA (TOTP armé)

Quand `OPS_DASHBOARD_TOTP_SECRET` est posé, le Basic seul est refusé (sinon la
2FA serait contournable). Le client échange ses identifiants **+ code TOTP**
contre un JWT :

```bash
curl -X POST https://ops.omnividens.fr/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"…","totp_code":"123456"}'
# -> {"token":"eyJ…","token_type":"bearer","expires_in_minutes":720}

curl https://ops.omnividens.fr/api/agents -H "Authorization: Bearer eyJ…"
```

Le secret TOTP s'enrôle dans une app d'authentification (Aegis, Google
Authenticator…) via son URI :

```bash
python -c "import pyotp; print(pyotp.totp.TOTP('LE_SECRET').provisioning_uri(name='admin', issuer_name='Argos Ops'))"
```

> Note : la SPA React n'embarque pas encore d'écran de login JWT. Tant qu'il
> n'existe pas, garder le **Basic sans TOTP** comme baseline pour l'accès
> navigateur ; la 2FA TOTP est destinée à l'accès API (et au futur écran login).

## Configuration Caddy

Insérer [`infra/caddy/ops.Caddyfile`](../infra/caddy/ops.Caddyfile) dans le
Caddyfile prod, remplacer les IP autorisées + le hash Basic :

```bash
caddy hash-password --plaintext 'MON_MOT_DE_PASSE'   # -> $2a$14$…
docker exec sechunter-caddy-1 caddy reload --config /etc/caddy/Caddyfile
```

S'assurer que le DNS `ops.omnividens.fr` (A → 204.168.171.71) résout avant le
reload pour la délivrance du certificat Let's Encrypt.

## Checklist de mise en service

- [ ] DNS `ops.omnividens.fr` → serveur prod
- [ ] `infra/caddy/ops.Caddyfile` adapté (IP réelles + hash bcrypt) et chargé
- [ ] `.env` applicatif : `OPS_DASHBOARD_BASIC_AUTH_*` + `JWT_SECRET` posés
- [ ] (optionnel) `OPS_DASHBOARD_TOTP_SECRET` + secret enrôlé dans l'app 2FA
- [ ] Vérifier : accès hors IP autorisée → `403` ; sans creds → `401` ;
      `/api/health` répond `200`
