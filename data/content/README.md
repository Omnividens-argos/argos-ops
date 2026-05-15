# `data/content/`

Queue locale des drafts de posts sociaux produits par le skill `content-writer`
(P9-DRAFT, 2026-05-14).

## Workflow actuel (P9-DRAFT — mode local-draft only)

1. `/draft-content <channel> <topic>` génère un fichier dans `drafts/`
2. Le fondateur valide / édite manuellement le draft
3. Le fondateur copie-colle le body dans le canal (LinkedIn / Mastodon / X)
   et publie
4. Le fondateur édite le frontmatter du draft :
   - `status: posted`
   - `posted_at: YYYY-MM-DDTHH:MM`
   - `url_posted: <permalink du post>`

Tant que P11 (connecteurs sociaux) n'est pas livré, **aucun posting
automatique**.

## Workflow futur (P9 full, post-P11)

Un agent `ContentBot` lira cette queue, filtrera les drafts `status: validated`,
les soumettra à `ClaudeJudge` (P14), et postera automatiquement via les
connecteurs `argos_ops/integrations/{linkedin,mastodon}.py` (Reddit retiré
par [D-022](../../docs/DECISIONS.md#d-022--retrait-d%C3%A9finitif-de-reddit-du-p%C3%A9rim%C3%A8tre-argos-ops)).

L'engagement (likes / comments / reshares) sera récupéré J+1 et loggé dans
`interactions.judge_score`.

## Convention de nommage

```
drafts/YYYY-MM-DD-<channel>-<slug>.md
```

- `YYYY-MM-DD` = date de création (TZ Paris)
- `<channel>` ∈ `{linkedin, mastodon, x}`
- `<slug>` = kebab-case du topic, tronqué à 50 chars

## Statuts

| Status | Sens | Qui transitionne |
|--------|------|------------------|
| `draft` | Sortie brute du skill, peut nécessiter ajustement | skill `content-writer` (création) |
| `validated` | Le fondateur a relu, OK pour publier | fondateur (manuel) |
| `posted` | Publié sur le canal | fondateur (manuel jusqu'à P11, ContentBot ensuite) |
| `rejected` | Pas publié, raison dans le frontmatter ou en commentaire | fondateur (manuel) |

## Liens

- Skill : `.claude/skills/content-writer/SKILL.md`
- Slash command : `.claude/commands/draft-content.md`
- Plan complet : `docs/ARGOS_OPS_PLAN.md` § Partie 9
