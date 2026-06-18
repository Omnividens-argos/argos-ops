"""Pôle 6 — Direction (archi v2, S6).

Pilote, arbitre et rend des comptes. C'est le pôle **transversal** : son agent
lit la mémoire de **tous** les autres pôles (``reads_cross_pole: ["*"]``) pour en
faire une vue d'ensemble — santé de la flotte, OKR, board pack, journal des
décisions, changelog, roadmap publique, feedback produit, triage des bugs.

Les **scripts** (bras déterministes) réutilisent les briques pures existantes des
agents legacy (:mod:`argos_ops.agents.okr_tracker`, :mod:`~argos_ops.agents.decision_logger`,
:mod:`~argos_ops.agents.feedback_aggregator`, :mod:`~argos_ops.agents.bug_triage`,
:mod:`~argos_ops.agents.changelog_bot`, :mod:`~argos_ops.agents.roadmap_publisher`,
:mod:`~argos_ops.agents.board_reporter`) — **aucun re-port** — et écrivent leur
mémoire ; le :class:`~argos_ops.poles.direction.agent.DirectionAgent` lit cette
mémoire (+ celle de toute la flotte en cross-pôle) et synthétise un plan
d'oversight priorisé.

**Garde-fou central (« le LLM propose, Python tranche »)** : la
:func:`~argos_ops.poles.direction.release.release_blocking` gèle la **publication**
d'artefacts publics (release notes / changelog / roadmap) tant qu'un bug **P0**
est ouvert ou qu'un pôle est en santé **critique**. Strict miroir du gel Bloctel
de la Vente / de la conformité de la Finance / du breaker ``ad_spend_runaway`` de Pub.

100 % fichiers / local-first (D-017) : tout vient des snapshots
``data/poles/direction/…`` et de la mémoire des pôles (aucune DB, aucune API tierce).
"""
