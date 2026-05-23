---
description: Lance RoadmapPublisher — génère la roadmap publique depuis l'Annexe D interne (codes sprint retirés). Sortie data/public/roadmap.md.
---

# /publish-roadmap

Slash command Claude Code invoquée manuellement (mensuel) ou Task Scheduler.

## Procédure

1. Lance `uv run python scripts/run_roadmap_publisher.py`.
2. **Si `silence (no entries)`** : Annexe D vide ou non parsable.
3. **Si OK** : `data/public/roadmap.md` régénérée intégralement. Discord jaune posté.
4. Founder revue → push sur le site public (`omnividens.fr/roadmap` ou équivalent).

## Notes

- Source unique : `docs/ARGOS_OPS_PLAN.md` Annexe D (depuis 2026-05-23, commit `4f287a7`).
- Le parser détecte `### N. Service` puis `- [x] ✅ **Bot** · ...` / `- [~] 🟡 ...` / `- [ ] ⬜ ...`.
- Codes sprint internes (`P22.X`, `Sprint N`) retirés de la sortie publique.
- Date de livraison conservée (mois année), pas le code interne.
- Idempotent : la roadmap publique est intégralement réécrite à chaque run.
- Read-only sur l'Annexe D — ne modifie jamais le plan interne.
- Breaker : `RoadmapPublisher` (P15).
