"""Pôle 5 — Finance & Conformité (archi v2, S5).

Encaisse, anticipe, déclare et garantit la conformité. Les **scripts** (bras
déterministes) réutilisent les briques pures existantes
(:mod:`argos_ops.finance`, :mod:`argos_ops.integrations.stripe_client`,
:mod:`argos_ops.compliance`, :mod:`argos_ops.sales.templates`) — **aucun
re-port** — et écrivent leur mémoire ; le :class:`~argos_ops.poles.finance.agent.FinanceAgent`
lit cette mémoire (+ celle de la Vente en cross-pôle) et synthétise un plan
d'actions priorisé, borné par le garde-fou conformité (« Python tranche »).

100 % fichiers / local-first (D-017) : aucun appel Stripe/DB en lecture cockpit
(tout vient des snapshots ``data/poles/finance/…``), aucune valeur secrète ici.
"""
