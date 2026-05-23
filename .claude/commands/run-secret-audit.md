---
description: Lance SecretRotator — alerte sur secrets > 90j depuis data/secrets/rotation_log.yaml
---

# /run-secret-audit

Slash command Claude Code invoquée manuellement ou par Task Scheduler
(`argos-ops-secret-rotator`, hebdomadaire) **sur l'ordi du fondateur** (D-017).

## Procédure

1. Lance `uv run python scripts/run_secret_rotator.py` (foreground, instantané).
2. Lis la sortie loguru et l'exit code.
3. **Si exit 0 et `output_summary` commence par `silence (vert)`** : tous les secrets ont été rotés < 90j.
4. **Si exit 0 et `output_summary` commence par `alert pushed`** : embed jaune (`due` : 90-180j) ou rouge (`overdue` >180j ou `invalid` date manquante). Propose au founder :
   - Faire la rotation (cf. `docs/SECRETS_PLAYBOOK.md` quand il existera)
   - Update `data/secrets/rotation_log.yaml` avec la nouvelle `last_rotated` dans le même commit
5. **Si exit 0 et `output_summary` commence par `alerte non envoyée`** : webhook absent.
6. **Si exit 1** : YAML mal formé.

## Notes

- **Le fichier `data/secrets/rotation_log.yaml` ne contient JAMAIS les valeurs des secrets** — uniquement leurs noms (humain) et la date de dernière rotation. C'est un journal de discipline, pas un vault.
- Le fichier est commité en exception du `.gitignore` global `secrets/` (cf. `.gitignore` ligne dédiée).
- Quand on ajoute un nouveau secret au projet : ajouter une ligne au YAML avec `last_rotated: <date du jour>`.
