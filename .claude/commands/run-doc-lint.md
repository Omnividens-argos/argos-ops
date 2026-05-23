---
description: Lance DocLinter — détecte les liens internes morts dans docs/, README.md, CLAUDE.md. Silence Discord si tout OK.
---

# /run-doc-lint

Slash command Claude Code invoquée manuellement ou par Task Scheduler
(`argos-ops-doc-lint`, hebdomadaire) **sur l'ordi du fondateur** (D-017).

## Procédure

1. Lance `uv run python scripts/run_doc_linter.py` (foreground, ~1 s).
2. **Si `silence (vert)`** : 0 lien cassé (RAS).
3. **Si embed jaune** (anchor manquant) : un heading a été renommé, le slug ne match plus. Liste les fichiers + lignes concernés, propose de fix.
4. **Si embed rouge** (file manquant) : un lien vers un fichier qui n'existe plus (fichier déplacé / supprimé). URGENT car le markdown casse pour les lecteurs.
5. **Si `silence (aucun doc)`** : pas de markdown trouvé sous le root scanné (impossible en pratique).

## Notes

- Scan portée par les globs `docs/**/*.md`, `README.md`, `CLAUDE.md` (cf. `DOCS_GLOBS`).
- Pas de check des liens externes (HTTP) — c'est un check rapide local-only (D-017).
- Slug GitHub-style : minuscules + tirets + ponctuation virée.

## Voir aussi

- Code : [argos_ops/agents/doc_linter.py](../../argos_ops/agents/doc_linter.py)