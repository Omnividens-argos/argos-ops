---
name: content-scheduler
description: Choisit l'heure et le jour optimaux pour publier un draft social sur LinkedIn / Mastodon / Reddit r/netsec / X, en respectant les fenêtres d'engagement de chaque canal + la règle 9:1 Reddit + un espacement minimal entre posts d'un même canal. Utilise ce skill quand le user demande de planifier un draft validé, de scheduler une queue de drafts, ou pendant /schedule-content. Pas de posting API — le skill retourne juste un timestamp suggéré que le fondateur (ou ContentBot P9 full après P11) applique.
---

# content-scheduler

Skill **éditorial planificateur**. À ne pas confondre avec un cron — ce
skill décide **quand** un post devrait sortir, pas **comment** il est posté.
Le posting est géré par P11 (connecteurs sociaux) en mode automatique
ou par le fondateur manuellement jusqu'à P11 live.

> **Pourquoi un skill et pas du code Python pur** : les fenêtres
> d'engagement optimal évoluent (les algos LinkedIn / Mastodon / Reddit
> changent) et dépendent de l'audience FR / EN / DACH. Garder ce skill
> en markdown permet d'ajuster les heuristiques sans toucher le code.
> Le calcul d'horodatage exact reste déterministe côté Python (helper
> futur `argos_ops/scheduler.py` si besoin de l'industrialiser P11+).

## Fenêtres canoniques par canal (audience BtoB tech FR + EN, 2026)

| Canal | Jours forts | Heures fortes (TZ Paris) | Espacement min entre 2 posts | Note |
|---|---|---|---|---|
| **LinkedIn** | Mardi / Mercredi / Jeudi | 7h30-9h30 + 12h-13h + 17h30-18h30 | 24 h | Audience hits le feed le matin avant standup et en pause déjeuner. Pas le vendredi soir, pas le weekend. |
| **Mastodon (infosec.exchange)** | Tous les jours sauf dimanche | 9h-11h + 14h-17h + 21h-22h | 4 h | Audience tech infosec mondiale → couvre les fuseaux US Pacific et Europe. Pas le dimanche matin. |
| **Reddit r/netsec** | Lundi / Mardi / Mercredi | 14h-18h (Paris) = matinée US Eastern | 7 jours minimum entre 2 posts perso (anti-spam karma) | Règle 9:1 stricte : 9 commentaires utiles non promo avant 1 post produit. Audience US-skewed. |
| **X / Twitter** | Mardi / Mercredi / Jeudi | 12h + 18h | 12 h | Canal **bas priorité** (Free tier supprimé). Si présence maintenue, minimaliste. |

## Inputs

- `draft_path` — chemin du draft markdown dans `data/content/drafts/`
- `(optionnel) target_date` — date cible explicite (format YYYY-MM-DD).
  Sinon, le skill propose la prochaine fenêtre optimale à partir de
  maintenant.
- `(optionnel) horizon_days` — nombre de jours à scanner pour trouver
  un créneau (défaut 7)

## Outputs

Patch le frontmatter du draft :

```yaml
status: validated
scheduled_for: 2026-05-15T08:00+02:00   # ISO 8601 avec offset TZ Paris
scheduling_rationale: "Mercredi matin LinkedIn — fenêtre 7h30-9h30, audience BtoB FR au standup. Espacement 26 h vs dernier post LinkedIn (2026-05-14 06:00)."
```

Le `status: draft → validated` est cohérent avec le workflow documenté
dans [`data/content/README.md`](../../data/content/README.md). Tant que
P11 n'est pas livré, le fondateur poste manuellement à l'heure dite.
Quand P11 sera live, ContentBot Python lira la queue `validated` et
posera automatiquement au `scheduled_for`.

## Procédure

### 1. Lecture du draft

- Charger le frontmatter (`channel`, `status`, `topic`, etc.)
- Refuser si `status != "draft"` (déjà validé / posté / rejeté → l'humain
  doit reset à `draft` s'il veut re-scheduler)

### 2. Lecture de l'historique récent du canal

- Lister les fichiers `data/content/drafts/*.md` avec
  `channel == draft.channel` ET `posted_at != null` ET `posted_at >
  now - 30 jours`
- Extraire les `posted_at` pour calculer le dernier post du canal
- Si Reddit : compter les `posted_at` Reddit sur 7 jours glissants — si
  ≥ 1, refuser de scheduler un 2e post (espacement min 7 jours)

### 3. Choix du créneau

- Si `target_date` fourni :
  - Trouver la fenêtre d'engagement du canal qui contient ou suit la
    date
  - Si elle viole l'espacement min vs dernier post → re-proposer le
    prochain créneau valide
- Sinon :
  - Scanner les `horizon_days` prochains jours (TZ Paris)
  - Filtrer les jours forts du canal
  - Filtrer les heures fortes du canal
  - Respecter l'espacement min vs dernier post du canal
  - Préférer le créneau le plus proche

### 4. Validation finale

Afficher au user :

- Le `scheduled_for` proposé + jour de la semaine + heure
- Le `rationale` (pourquoi cette fenêtre, vs dernier post)
- Demander : « OK pour valider et scheduler ? »

Si oui : éditer le frontmatter du draft (`status: validated` +
`scheduled_for` + `scheduling_rationale`).

### 5. Notif Discord (optionnel)

Pousser sur `DISCORD_WEBHOOK_OPS_LOGS` :
« Draft scheduled : [<channel>] <topic> · `<scheduled_for>` ·
`data/content/drafts/<file>` ».

## Anti-patterns à refuser

- **Reddit promo < 7 jours après dernier post Reddit** — règle 9:1 +
  espacement. Refuser, proposer Mastodon ou LinkedIn à la place.
- **LinkedIn weekend** — refuser, proposer mardi/mercredi/jeudi le plus
  proche.
- **Reddit dimanche** — audience US descend, traffic perdu.
- **Cluster temporel** (3 posts LinkedIn en 48h) — refuser, étaler.
- **Heure « morte »** (LinkedIn samedi 23h, Mastodon dimanche 4h) —
  refuser.
- **`status != "draft"`** — l'humain doit explicitement reset si il
  veut re-scheduler.

## Évolution prévue

- **Calibration trimestrielle** : audit des `posted_at` + engagement
  J+1 (via `interactions.judge_score` rempli post-P11 quand on
  pull l'engagement réel) → ajuster les fenêtres si on observe que
  l'audience Argos publique réagit à des heures différentes des
  défauts secteur
- **Intégration ContentBot P9 full** : quand P11 + ContentBot agent
  Python seront live, ce skill restera la source de vérité pour le
  scheduling. ContentBot Python appellera Claude Code avec ce skill
  pour décider du `scheduled_for` puis poussera via les connecteurs
  P11 au moment dit

## Liens

- Skill cousin : `content-writer` (qui produit le draft) +
  `seo-brief-writer` (briefs blog longform)
- Drafts à scheduler : `data/content/drafts/`
- Workflow complet : `data/content/README.md`
- Plan P9 full : `docs/ARGOS_OPS_PLAN.md` § Partie 9
- Plan P11 connecteurs sociaux : `docs/ARGOS_OPS_PLAN.md` § Partie 11
