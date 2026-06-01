# Meta / Facebook Page — setup OAuth (action manuelle fondateur)

> **Quand** : avant de publier en live sur la Page Facebook Argos. Tant que
> ce n'est pas fait, le connecteur `argos_ops/social/meta.py` tourne en
> **shadow** (il drafte mais ne poste rien) — aucune erreur, juste pas de
> publication.
>
> **Coût** : 0 € (publication organique gratuite). À ne pas confondre avec
> **Meta Ads** (payant, `META_ADS_*`) qui dépend d'un budget pub validé.
>
> **Durée** : ~20-30 min (le plus long = créer l'app + récupérer le token).

---

## Ce qu'on veut obtenir

Un **token d'accès de Page long-lived** (`META_PAGE_ACCESS_TOKEN`) + l'**ID
de la Page** (`META_PAGE_ID`), avec le scope `pages_manage_posts`. Le
connecteur poste alors via `POST /{page-id}/feed`.

> Le token de Page **dérivé d'un token utilisateur long-lived n'expire pas**
> tant que le mot de passe / les permissions ne changent pas — pratique, mais
> à re-générer en cas de changement (cf. § Rotation).

---

## Étapes

### 1. Page Facebook Argos

Si pas encore fait : créer une **Page Facebook** « Argos » / « Omnividens »
(pas un profil perso). Noter qu'on cible les **patrons de TPE/PME** (persona
non-technique) — bio + visuel rassurants, lien `https://omnividens.fr`.

### 2. App Meta développeur

1. https://developers.facebook.com → **My Apps** → **Create App**
2. Type : **Business**. Nommer « Argos Ops ».
3. Dans l'app → **Add Product** → **Facebook Login** (suffit pour récupérer
   un token via l'Explorer ; pas besoin d'un flow web complet ici).
4. Lier la Page : **App settings** → **Business** / associer la Page Argos
   (ou via Meta Business Suite → Paramètres → Comptes → Pages).

### 3. Récupérer un token utilisateur avec les bons scopes

1. Ouvre le **Graph API Explorer** :
   https://developers.facebook.com/tools/explorer/
2. Sélectionne ton app « Argos Ops » en haut.
3. **Add a permission** → coche : `pages_show_list`, `pages_read_engagement`,
   `pages_manage_posts`.
4. **Generate Access Token** → connecte-toi + autorise. Tu obtiens un **token
   utilisateur court** (1-2h).

### 4. Échanger en long-lived + récupérer le token de Page

Deux options.

**Option A (tout dans l'Explorer, le plus simple) :**
1. Dans l'Explorer, requête `GET /me/accounts`. La réponse liste tes Pages
   avec, pour chacune, un `access_token` (déjà un token de Page) + son `id`.
2. Si le token utilisateur source était long-lived, ces tokens de Page le
   sont aussi. Pour forcer le long-lived côté utilisateur d'abord, fais
   l'option B puis re-fais `GET /me/accounts`.

**Option B (échange explicite long-lived, recommandé) :**
```
GET https://graph.facebook.com/v21.0/oauth/access_token
  ?grant_type=fb_exchange_token
  &client_id=<APP_ID>
  &client_secret=<APP_SECRET>
  &fb_exchange_token=<TOKEN_UTILISATEUR_COURT>
```
→ renvoie un **token utilisateur long-lived** (60j). Re-fais ensuite
`GET /me/accounts?access_token=<LONG_LIVED_USER_TOKEN>` → le `access_token`
de ta Page est alors long-lived.

> `APP_ID` / `APP_SECRET` : **App settings → Basic**. L'`APP_SECRET` est un
> secret — ne le commit jamais, et ne le mets dans `.env.local` que si un
> script en a besoin (le connecteur n'en a pas besoin, il utilise directement
> le token de Page).

### 5. Renseigner `.env.local`

Ajouter (jamais dans `.env.example`, jamais commité) :

```dotenv
META_PAGE_ID=123456789012345
META_PAGE_ACCESS_TOKEN=EAA...le-long-token-de-Page...
# META_GRAPH_API_VERSION reste v21.0 (bump seulement si Meta la déprécie).
```

> Rappel sécu (cf. mémoire `feedback_secrets_via_ide_leak`) : éviter de
> coller le token dans un `.env.local` **ouvert dans l'IDE** (les diffs
> remontent dans les system-reminders). Préférer un éditeur externe ou une
> commande PowerShell, fichier fermé. Le filtre loguru redacte déjà tout
> token `EAA...` qui passerait dans un log.

### 6. Tester

```powershell
uv run python scripts/test_meta.py --dry-run   # shadow, ne poste rien
uv run python scripts/test_meta.py             # poste un message de test live
```

Sortie attendue en live :
```
[+] Mode      : LIVE
...
[OK] Publié — URL : https://www.facebook.com/123456789_987654321
```
Supprimer le post de test ensuite si voulu.

---

## App Review — quand est-ce nécessaire ?

- **Ta propre Page, toi admin, app en mode développement** : `pages_manage_posts`
  fonctionne **sans App Review** (tu es admin/testeur de l'app).
- **Passage en mode Live / poster pour des Pages tierces** : Meta exige une
  **App Review** de `pages_manage_posts` (quelques jours). Pour notre usage
  (notre propre Page Argos), le mode dev suffit — pas de review bloquante.

---

## Rotation / révocation

Le token de Page se révoque depuis **Meta Business Suite → Paramètres →
Sécurité** ou en changeant les permissions de l'app. En cas de fuite ou de
rotation (cf. SecretRotator > 90j) : révoquer, re-générer (étapes 3-4),
mettre à jour `.env.local`. Aucun autre changement nécessaire.

---

## Persona — rappel important

Ce canal vise **les patrons de TPE/PME non-techniques** (« Patrick »), pas le
public cyber-expert des autres réseaux. Le skill `meta-writer` applique un
**anti-FUD strict** et un **zéro jargon** — ne jamais poster sur la Page un
contenu technique destiné à LinkedIn/Mastodon. Cf.
[`.claude/skills/meta-writer/SKILL.md`](../.claude/skills/meta-writer/SKILL.md).

---

## Liens

- Connecteur : [`argos_ops/social/meta.py`](../argos_ops/social/meta.py)
- Skill : [`.claude/skills/meta-writer/SKILL.md`](../.claude/skills/meta-writer/SKILL.md)
- Slash : [`/draft-meta`](../.claude/commands/draft-meta.md)
- Script test : [`scripts/test_meta.py`](../scripts/test_meta.py)
- Vars `.env` : section `# --- Meta / Facebook Page ---` de [`.env.example`](../.env.example)
