---
description: Lance ADRWriter — drafte un ADR (Architecture Decision Record) au format MADR depuis un input structuré. Écrit docs/adr/ADR-NNNN-<slug>.md. Idempotent par slug.
---

# /write-adr

Slash command Claude Code invoquée à la demande pour formaliser une décision
d'architecture après une PR ou une discussion :

```
/write-adr migrer-vers-postgres-16
```

## Procédure

1. Récupère le slug depuis l'argument (ex : `migrer-vers-postgres-16`). Si pas de slug fourni, demande au founder un titre.
2. Demande au founder les 3 sections clés (humain-in-the-loop) :
   - **Contexte** : pourquoi cette décision est nécessaire
   - **Décision** : ce qui a été choisi
   - **Conséquences** : ce que ça implique (positif + négatif + abandonné)
3. Lance `uv run python scripts/run_adr_writer.py <slug>` (foreground, < 1 s) avec les sections en entrée (le script lit un stdin JSON ou un fichier draft que Claude prépare).
4. **Si exit 0** : ADR écrit dans `docs/adr/ADR-NNNN-<slug>.md`. Numéro auto-incrémenté (ou ré-utilisé si le slug existe déjà). Output `adr=ADR-NNNN action=created|updated`.
5. Propose au founder de relire avant commit.

## Notes

- Format = MADR léger : titre + statut (proposed/accepted/superseded) + date + 3 sections.
- Idempotent par slug — ré-exécuter avec le même slug update l'ADR existant et garde son numéro.
- Pas d'auto-publication sur GitHub. Le founder commit manuellement le markdown généré.

## Voir aussi

- Code : [argos_ops/agents/adr_writer.py](../../argos_ops/agents/adr_writer.py)
- Convention MADR : https://adr.github.io/madr/