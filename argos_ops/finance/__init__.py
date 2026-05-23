"""Helpers comptabilité Argos Ops (Sprint 10).

Modules :

- :mod:`argos_ops.finance.tva` — calcul TVA française (CA3, taux normal 20 %)
- :mod:`argos_ops.finance.cash_flow` — forecast cash flow 30/60/90 jours
- :mod:`argos_ops.finance.reconcile` — rapprochement Stripe payouts ↔ Qonto
- :mod:`argos_ops.finance.expense_csv` — parsing CSV export Qonto

Tous les calculs sont en EUR (Argos est facturé en EUR uniquement) avec
:class:`decimal.Decimal` pour éviter les erreurs flottantes sur la compta.
"""
