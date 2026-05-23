---
description: Lance ChangelogBot — génère un changelog Markdown depuis git log entre 2 refs (ou 100 derniers commits). Groupé par conventional commit type.
---

# /draft-changelog

Slash command Claude Code invoquée manuellement (à chaque release).

## Procédure

1. Lance `uv run python scripts/run_changelog_bot.py [from_ref] [to_ref]`.
   - Sans arg : prend le tag git le plus récent comme base.
   - Avec args : `from_ref` et optionnellement `to_ref` (défaut HEAD).
2. **Si `silence (no commits ...)`** : range vide → vérifier les refs.
3. **Si OK** : changelog écrit dans `data/public/changelog_<slug>.md`. Discord jaune posté.
4. Peaufiner manuellement (regrouper les feat redondantes, virer le bruit "chore").
5. Optionnel : `cp data/public/changelog_<slug>.md CHANGELOG.md` pour un changelog cumulatif.

## Notes

- Format conventional commits parsé : `feat / fix / chore / refactor / docs / test / perf`, le reste → `other`.
- Breaking changes (`feat!:` ou `fix!:`) annotés 💥.
- Idempotent : un changelog déjà créé n'est pas écrasé (relancer avec `--force` côté script si besoin — pas de flag actuel, supprimer le fichier d'abord).
- Lecture seule git (subprocess `git log`).
- Pas de fetch remote ; on lit l'historique local.
- Breaker : `ChangelogBot` (P15).
