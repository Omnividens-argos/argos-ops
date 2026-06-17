"""Bras déterministes (scripts) du pôle Finance & Conformité (archi v2, S5).

Chaque script hérite de :class:`~argos_ops.poles.base.BaseScript`, fait du travail
pur et idempotent (lit un snapshot ``data/poles/finance/…`` ou réutilise une brique
pure existante, calcule, écrit sa mémoire) et ne décide rien : c'est le
:class:`~argos_ops.poles.finance.agent.FinanceAgent` qui lit cette mémoire et agit.
Les faits « docs fiscaux/légaux » (CA3, RGPD, AI Act, incidents, échéances de
contrat) sont écrits avec le flag ``important`` (protégés du nettoyage). 100 %
fichiers / local-first (D-017).
"""

from __future__ import annotations

from argos_ops.poles.finance.scripts.ai_act_compliance import AIActComplianceScript
from argos_ops.poles.finance.scripts.burn_rate_monitor import BurnRateMonitorScript
from argos_ops.poles.finance.scripts.contract_deadline import ContractDeadlineScript
from argos_ops.poles.finance.scripts.expense_auditor import ExpenseAuditorScript
from argos_ops.poles.finance.scripts.finance_bot import FinanceBotScript
from argos_ops.poles.finance.scripts.incident_logger import IncidentLoggerScript
from argos_ops.poles.finance.scripts.invoice_predictor import InvoicePredictorScript
from argos_ops.poles.finance.scripts.reconcile_bot import ReconcileBotScript
from argos_ops.poles.finance.scripts.rgpd_auditor import RGPDAuditorScript
from argos_ops.poles.finance.scripts.tax_bot import TaxBotScript
from argos_ops.poles.finance.scripts.vendor_contract_watcher import VendorContractWatcherScript

# Ordre = ordre d'exécution cron canonique du pôle (cf. pole.yaml).
FINANCE_SCRIPTS = (
    FinanceBotScript,
    InvoicePredictorScript,
    ExpenseAuditorScript,
    ReconcileBotScript,
    BurnRateMonitorScript,
    VendorContractWatcherScript,
    TaxBotScript,
    RGPDAuditorScript,
    AIActComplianceScript,
    ContractDeadlineScript,
    IncidentLoggerScript,
)

__all__ = [
    "FINANCE_SCRIPTS",
    "AIActComplianceScript",
    "BurnRateMonitorScript",
    "ContractDeadlineScript",
    "ExpenseAuditorScript",
    "FinanceBotScript",
    "IncidentLoggerScript",
    "InvoicePredictorScript",
    "RGPDAuditorScript",
    "ReconcileBotScript",
    "TaxBotScript",
    "VendorContractWatcherScript",
]
