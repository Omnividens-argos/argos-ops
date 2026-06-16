"""Modèle d'une capability inter-agents (P21, file-based)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CapabilityPermission = Literal["read", "write_back"]
# « react » (push) reste hors périmètre v1, comme la conception DB d'origine.

WRITE_BACK_KIND_PREFIX = "advice."


@dataclass(frozen=True)
class CapabilityRule:
    """Un droit déclaré : ``subject`` consomme/écrit chez ``object``.

    - ``kind_filter`` : kinds de faits concernés (vide = tous).
    - ``tag_filter`` : tags requis (ET logique ; vide = pas de filtre).
    - ``enabled`` : toggle on/off sans supprimer la ligne (deny override
      pour ``read``, activation obligatoire pour ``write_back``).
    """

    subject: str
    object: str
    permission: CapabilityPermission
    kind_filter: tuple[str, ...] = ()
    tag_filter: tuple[str, ...] = ()
    enabled: bool = True
    notes: str | None = None

    def matches_fact(self, *, kind: str, tags: tuple[str, ...]) -> bool:
        """Le fait (kind + tags) passe-t-il les filtres de cette règle ?"""
        if self.kind_filter and kind not in self.kind_filter:
            return False
        return all(t in tags for t in self.tag_filter)


__all__ = ["WRITE_BACK_KIND_PREFIX", "CapabilityPermission", "CapabilityRule"]
