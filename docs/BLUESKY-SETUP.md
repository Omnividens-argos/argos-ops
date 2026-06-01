# Bluesky — setup credentials (action manuelle fondateur)

> **Quand** : avant de publier en live sur Bluesky. Tant que ce n'est pas
> fait, le connecteur `argos_ops/social/bluesky.py` tourne en **shadow**
> (il drafte mais ne poste rien) — aucune erreur, juste pas de publication.
>
> **Coût** : 0 €. L'API AT Protocol de Bluesky est **gratuite et illimitée**.
> Pas de tier payant, pas de quota à arbitrer (contrairement à X). C'est le
> quick win gratuit du Sprint contenu.
>
> **Durée** : ~5 minutes.

---

## Pourquoi un *app password* et pas le mot de passe du compte

Bluesky permet de générer des **app passwords** : des mots de passe
secondaires, révocables individuellement, qui n'ont pas accès aux réglages
critiques du compte (ne peuvent ni changer le mdp principal, ni supprimer
le compte). Si le token fuite (log, commit accidentel), on le révoque sans
toucher au compte. **Ne jamais mettre le vrai mot de passe du compte dans
`.env.local`.**

---

## Étapes

### 1. Compte Bluesky Omnividens

Si pas encore fait : créer un compte sur https://bsky.app.

- Handle suggéré : `omnividens.bsky.social` (ou un domaine custom plus tard,
  ex. `omnividens.fr` vérifié comme handle — optionnel, étape avancée).
- Renseigner bio + avatar + lien `https://omnividens.fr` (cohérence brand).

### 2. Générer l'app password

1. https://bsky.app → **Settings** (Réglages)
2. **Privacy and Security** → **App Passwords**
3. **Add App Password** → nommer `argos-ops`
4. Bluesky affiche un mot de passe au format `xxxx-xxxx-xxxx-xxxx`.
   **Le copier maintenant** — il n'est plus ré-affiché ensuite.

> Laisser décochée l'option « Allow access to your direct messages » sauf
> besoin explicite — Argos ne poste que des statuts publics.

### 3. Renseigner `.env.local`

Ajouter (jamais dans `.env.example`, jamais commité) :

```dotenv
BLUESKY_HANDLE=omnividens.bsky.social
BLUESKY_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
# BLUESKY_PDS_URL reste https://bsky.social (défaut), ne pas toucher.
```

> Rappel sécu (cf. mémoire `feedback_secrets_via_ide_leak`) : éviter de
> coller le token dans un fichier ouvert dans l'IDE (les diffs remontent
> dans les system-reminders). Préférer un éditeur externe ou une commande
> PowerShell scriptée, fichier fermé.

### 4. Tester le branchement

```powershell
uv run python scripts/test_bluesky.py --dry-run    # shadow, ne poste rien
uv run python scripts/test_bluesky.py              # poste un message de test live
```

- `--dry-run` valide que le client se construit sans toucher au réseau.
- Sans flag, et credentials remplis → poste réellement un court message de
  test et renvoie l'URL `https://bsky.app/profile/.../post/...`. Supprimer
  ce post de test ensuite si voulu.

Sortie attendue en live :

```
[+] Mode     : LIVE
...
[OK] Publié — URL : https://bsky.app/profile/omnividens.bsky.social/post/3k...
```

---

## Ce que le connecteur gère pour toi

- **Session** : `createSession` (handle + app password) → JWT éphémère.
- **Post** : `createRecord` sur la collection `app.bsky.feed.post`.
- **Rich text (facets)** : les URLs et les `#hashtags` présents dans le
  texte sont rendus **cliquables** automatiquement (Bluesky ne le fait pas
  tout seul). Un lien `https://omnividens.fr` dans un draft devient un vrai
  lien dans le post.
- **Limite** : 300 graphemes (le skill `bluesky-writer` borne en amont).

---

## Workflow de publication

1. `/draft-bluesky <topic>` → draft dans `data/content/drafts/` (status `draft`).
2. Valider visuellement, passer `status: validated`.
3. **Manuel** (sans credentials) : copier-coller dans https://bsky.app.
4. **Semi-auto** (credentials remplis) :
   `uv run python scripts/test_bluesky.py --message "<body>"`.
5. **Auto** (P11 ContentBot full) : la queue `status: validated` sera
   publiée via le connecteur, le canal `bluesky` étant déjà câblé dans
   `argos_ops/social/publisher.py`.

---

## Révocation / rotation

En cas de fuite ou rotation périodique (cf. SecretRotator > 90j) :
Settings → App Passwords → révoquer `argos-ops` → en regénérer un →
mettre à jour `.env.local`. Aucun autre changement nécessaire.

---

## Liens

- Connecteur : [`argos_ops/social/bluesky.py`](../argos_ops/social/bluesky.py)
- Skill : [`.claude/skills/bluesky-writer/SKILL.md`](../.claude/skills/bluesky-writer/SKILL.md)
- Slash : [`/draft-bluesky`](../.claude/commands/draft-bluesky.md)
- Script test : [`scripts/test_bluesky.py`](../scripts/test_bluesky.py)
- Vars `.env` : section `# --- Bluesky ---` de [`.env.example`](../.env.example)
