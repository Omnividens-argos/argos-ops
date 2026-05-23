"""Communication & RP — helpers partagés Sprint 5 (P22i LOT C).

Modules :

- :mod:`argos_ops.comm.brand` — règles de brand consistency (tagline,
  domaine canonique, disclosure AI Act, tonalité) consommées par
  BrandGuardBot et l'axe brand du skill ``claude-judge``.
"""

from __future__ import annotations

from argos_ops.comm.brand import (
    BRAND_TAGLINE,
    BrandIssue,
    audit_text,
    canonical_brand_rules,
)

__all__ = ["BRAND_TAGLINE", "BrandIssue", "audit_text", "canonical_brand_rules"]
