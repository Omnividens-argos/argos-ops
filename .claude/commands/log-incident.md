---
description: Scaffold un post-mortem d'incident sécurité interne (interactif)
---

# /log-incident

Slash command interactif pour logger un incident sécurité Argos Ops.

## Procédure

1. Demander au founder :
   - **Titre court** (1 phrase factuelle)
   - **Catégorie** parmi : `data_leak` / `intrusion` / `downtime` / `misconfig` / `other`
   - **Sévérité** parmi : `P0` (critique) / `P1` (majeur) / `P2` (modéré) / `P3` (mineur)

2. Appeler le scaffold via Python :

```python
from argos_ops.agents.incident_logger import scaffold_incident

result = scaffold_incident(
    title="<titre>",
    category="<categorie>",
    severity="<P0|P1|P2|P3>",
)
print(result.path)
```

3. Ouvrir le fichier généré `data/compliance/incidents/<YYYY-MM-DD>-<slug>.md`
   et demander au founder de remplir :
   - Chronologie (heures de détection / mitigation / résolution)
   - Impact (users, données, durée, notification CNIL)
   - Cause racine
   - Actions correctives + préventives
   - Lessons learned

4. Une fois rempli, suggérer de committer dans une branche dédiée
   `chore/incident-<slug>` (pas dans main directement — l'incident reste
   en revue interne).

## Notes

- **Idempotent** : re-lancer le même jour avec le même titre rend le même fichier.
- **Aucun push Discord** : les incidents restent locaux par défaut. Le founder
  décide s'il y a notification externe (CNIL si données perso, clients
  impactés, etc.).
- Notification CNIL obligatoire si fuite de données perso (RGPD art. 33, < 72h).
