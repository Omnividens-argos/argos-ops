---
id: changelog
role: reporting
references: argos_ops/poles/direction/changelog.py
guardrails:
  - Publication soumise au garde-fou release (gel si bug P0 ou pôle critique).
  - Groupement par conventional commit (feat/fix/perf/refactor/docs/test/chore).
---

Génère le **changelog** à partir du snapshot de commits (conventional commits
groupés par type). Artefact public — sa publication passe par le garde-fou release.
