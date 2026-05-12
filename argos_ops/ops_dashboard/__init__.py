"""Admin Control Panel Argos Ops (P16).

Backend FastAPI + frontend React. Sert ``ops.omnividens.fr`` une fois
routé via Caddy. Voir ``docs/ARGOS_OPS_PLAN.md`` § 16 et
``docs/UI_DECISIONS.md`` pour le design.

Phases :
- **16.A** (Sprint 1, en cours) — endpoints read-only + dashboard React lecture seule
- **16.B** — toggles, sliders intensity, run-now, breakers control (mutations)
- **16.C** — escalations queue + settings
- **16.D** — KB editor + KPIs avancés + 2FA TOTP
"""
