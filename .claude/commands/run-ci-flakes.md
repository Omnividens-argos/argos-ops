---
description: Lance CIFlakeTracker — repère les tests CI flaky (>= 20% failures sur les 50 derniers runs). Silence Discord si aucun.
---

# /run-ci-flakes

Slash command Claude Code invoquée manuellement ou par cron hebdomadaire
**sur l'ordi du fondateur** (D-017).

## Procédure

1. Lance `uv run python scripts/run_ci_flake_tracker.py` (foreground,
   ~10-30 sec selon le nombre de runs récents — l'API GitHub Actions
   paginate, on en récupère 50 par défaut).
2. Lis la sortie loguru et l'exit code.
3. **Si exit 0 et `output_summary` commence par `silence (vert)`** :
   aucun job CI au-dessus du seuil de flake (>= 20% failures + >= 3
   occurrences absolues sur 50 runs).
4. **Si exit 0 et `output_summary` commence par `alert pushed`** : un
   embed jaune liste les jobs flaky avec leur fail rate. Le founder
   doit :
   - Ouvrir l'historique GitHub Actions du job concerné
   - Identifier si c'est un test transient (timing, ordre, dépendance
     externe) ou un vrai bug latent
   - Décider : ouvrir une issue, isoler le test (`@pytest.mark.flaky`
     temporaire), ou fixer la cause racine
5. **Si exit 1** : `gh` non authentifié ou rate-limited. Vérifier
   `gh auth status`.

## Notes

- Source : API GitHub Actions via `gh api` (déjà authentifié sur la
  machine, pas besoin de PAT en clair).
- Repo par défaut : `Omnividens-argos/argos-ops` — override via
  l'argument du constructeur `CIFlakeTracker(repo=...)`.
- Pas de breaker associé — observation passive.
