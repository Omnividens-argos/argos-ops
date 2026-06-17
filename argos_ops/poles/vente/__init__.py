"""Pôle 4 — **Vente & Relation Client** (archi v2, S4) — le plus gros pôle.

Conversion + relation client : l'agent (``VenteAgent``) lit la **Veille**
(signaux d'achat : ``intent_signal`` / ``breach`` / ``cve`` / ``regulatory``) et le
**Marketing** (message) en cross-pôle, plus la mémoire de ses 12 scripts
déterministes, puis **synthétise un plan d'actions priorisé**.

Domaines (modules) :

- :mod:`~argos_ops.poles.vente.pipeline` — deals + scoring de risque (Kanban) ;
- :mod:`~argos_ops.poles.vente.inbox` — tri inbound + gate AI Act réponse humaine ;
- :mod:`~argos_ops.poles.vente.accounts` — santé / churn / upsell (RGPD § 22) ;
- :mod:`~argos_ops.poles.vente.support` — triage tickets P0/P1/P2 + SLA ;
- :mod:`~argos_ops.poles.vente.outreach` — leads / enrichissement / séquences /
  **Bloctel** (le garde-fou « Python tranche » qui gèle l'outbound) ;
- :mod:`~argos_ops.poles.vente.meetings` — RDV → iCal ;
- :mod:`~argos_ops.poles.vente.proposals` — devis / contrats ;
- :mod:`~argos_ops.poles.vente.plan` — synthèse du plan d'actions de l'agent.

100 % fichiers, local-first (D-017). Réutilise les briques pures
``argos_ops.{sales,cs,outbound}`` + ``argos_ops.compliance``.
"""

from __future__ import annotations
