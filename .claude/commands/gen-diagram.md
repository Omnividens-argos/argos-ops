---
description: Lance DiagramGenerator — génère un diagramme Mermaid (flowchart) à partir d'une spec YAML dans data/diagrams/<slug>.yaml. Écrit docs/diagrams/<slug>.md.
---

# /gen-diagram

Slash command Claude Code invoquée à la demande avec un slug en argument :

```
/gen-diagram pipeline-emailbot
```

## Procédure

1. Récupère le slug depuis l'argument utilisateur (ex : `pipeline-emailbot`).
2. Vérifie que `data/diagrams/<slug>.yaml` existe. Si non, demande au founder le contenu de la spec YAML (nodes + edges + direction + title).
3. Lance `uv run python scripts/run_diagram_generator.py <slug>` (foreground, < 1 s).
4. **Si exit 0** : le diagramme markdown a été écrit dans `docs/diagrams/<slug>.md`. Affiche le chemin et propose d'ouvrir le fichier.
5. **Si exit 1** : la spec est invalide (direction inconnue, edge vers un node inconnu, ID dupliqué, …). Lis l'erreur, propose au founder de corriger la spec YAML.

## Notes

- Format de spec YAML attendu : voir docstring de [`argos_ops/agents/diagram_generator.py`](../../argos_ops/agents/diagram_generator.py).
- Directions supportées : `LR` (gauche-droite, défaut), `TB` (top-bottom), `RL`, `BT`.
- Idempotent : ré-exécuter avec le même slug écrase la sortie. Aucune API externe.
- Pas de validation Mermaid à proprement parler — c'est de la sérialisation YAML → texte Mermaid (compatible GitHub render).

## Voir aussi

- Code : [argos_ops/agents/diagram_generator.py](../../argos_ops/agents/diagram_generator.py)