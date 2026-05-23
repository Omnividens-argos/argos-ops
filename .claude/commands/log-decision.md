---
description: Append une décision structurante au journal canonique docs/DECISIONS.md (interactif)
---

# /log-decision

Slash command interactif pour append une décision dans `docs/DECISIONS.md`.

## Procédure

1. Demander au founder :
   - **Titre court** (≤ 80 chars, factuel)
   - **Partie du plan** (ex : `P22.E`, `Annexe D §1`, `INFRA-02`)
   - **Décision** (1-2 phrases, ce qui est tranché)
   - **Pourquoi** (raison principale + alternatives écartées)
   - **Implication technique** (optionnel, code/infra impact)
   - **Annule** (optionnel, référence D-XXX précédente)
   - **Action de suivi** (optionnel, todo générée)

2. Appeler `append_decision` :

```python
from pathlib import Path
from argos_ops.agents.decision_logger import (
    DecisionDraft,
    DEFAULT_DECISIONS_PATH,
    append_decision,
)

draft = DecisionDraft(
    title="<titre>",
    partie="<partie>",
    decision="<décision>",
    pourquoi="<pourquoi>",
    implication_technique="<optionnel>",
    annule="<optionnel>",
    action_de_suivi="<optionnel>",
)
result = append_decision(draft, output_path=DEFAULT_DECISIONS_PATH)
print(f"{result.decision_id} appended={result.appended}")
```

3. Afficher l'ID généré (`D-NNN`) et le diff du fichier.

4. Suggérer un commit `docs: D-NNN — <titre>` dans une branche
   `chore/decision-<slug>` (jamais main direct).

## Garde-fous

- **Idempotent par titre** : si une décision avec le même titre existe
  déjà, on ne réécrit pas — `result.appended` retourne `False`.
- **ID auto-incrémenté** : pas de saisie manuelle, on prend `max(D-NNN) + 1`.
- **Tests** : tous les tests passent un `output_path` dans `tmp_path` —
  jamais le vrai `docs/DECISIONS.md`.
