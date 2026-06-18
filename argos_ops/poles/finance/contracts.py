"""Contrats du pôle Finance (archi v2, S5) — fournisseurs + clients.

Réutilise telle quelle (pas de re-port) :

- :mod:`argos_ops.agents.vendor_contract_watcher` — échéances d'annulation des
  contrats **fournisseurs** (tacite reconduction) depuis
  ``data/poles/finance/contracts/vendors.yaml`` ;
- :mod:`argos_ops.agents.contract_deadline` — échéances de renouvellement des
  contrats **clients** (60j) depuis ``data/poles/finance/contracts/clients.yaml``.

Les deux modules legacy exposent ``load_contracts`` / ``build_report`` ; on les
importe sous alias pour ne pas collisionner.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from argos_ops.agents.contract_deadline import (
    ContractDeadlineReport,
    ContractRenewal,
)
from argos_ops.agents.contract_deadline import (
    build_report as build_client_report,
)
from argos_ops.agents.contract_deadline import (
    load_contracts as load_client_contracts,
)
from argos_ops.agents.vendor_contract_watcher import (
    Contract,
    ContractReport,
)
from argos_ops.agents.vendor_contract_watcher import (
    build_report as build_vendor_report,
)
from argos_ops.agents.vendor_contract_watcher import (
    load_contracts as load_vendor_contracts,
)
from argos_ops.poles.config import POLES_DIR

FINANCE_POLE = "finance"


def contracts_dir(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / FINANCE_POLE / "contracts"


def vendors_path(*, poles_root: Path = POLES_DIR) -> Path:
    return contracts_dir(poles_root=poles_root) / "vendors.yaml"


def clients_path(*, poles_root: Path = POLES_DIR) -> Path:
    return contracts_dir(poles_root=poles_root) / "clients.yaml"


def vendor_contracts(*, poles_root: Path = POLES_DIR, today: date | None = None) -> list[Contract]:
    """Contrats fournisseurs + leur statut d'échéance d'annulation."""
    return load_vendor_contracts(vendors_path(poles_root=poles_root), today=today)


def vendor_report(*, poles_root: Path = POLES_DIR, today: date | None = None) -> ContractReport:
    return build_vendor_report(vendor_contracts(poles_root=poles_root, today=today))


def client_renewals(
    *, poles_root: Path = POLES_DIR, today: date | None = None
) -> list[ContractRenewal]:
    """Contrats clients + leur prochaine échéance de renouvellement."""
    return load_client_contracts(clients_path(poles_root=poles_root), today=today)


def client_report(
    *, poles_root: Path = POLES_DIR, today: date | None = None
) -> ContractDeadlineReport:
    return build_client_report(client_renewals(poles_root=poles_root, today=today))


__all__ = [
    "Contract",
    "ContractDeadlineReport",
    "ContractRenewal",
    "ContractReport",
    "client_renewals",
    "client_report",
    "clients_path",
    "contracts_dir",
    "vendor_contracts",
    "vendor_report",
    "vendors_path",
]
