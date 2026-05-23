# Argos Ops

> Flotte d'agents IA qui automatise l'acquisition, la conversion, le support
> et l'admin de **Argos / SecHunter / Omnividens** — SaaS pentest BtoB sur
> [omnividens.fr](https://omnividens.fr).
>
> Pilotée par Claude Code via des slash commands périodiques. Contrainte :
> **0 € de SaaS récurrent** en plus de Claude Pro/Max.

---

## Architecture en 4 couches

```
ACQUISITION       CONVERSION         RÉTENTION
ContentBot        EmailBot in        SupportBot
SEOBot            DemoBot (P2)       FinanceBot
AdBot             CallerBot (P2)     AnalyticsBot
OutboundBot
```

Toutes les couches lisent et écrivent dans un **CRM + Knowledge Base** central
(Postgres + pgvector + Redis), supervisé par un **agent-juge IA** (Claude) et
des **circuit breakers** automatiques.

Voir [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) pour le détail.

---

## Status

🚧 **En cours de bootstrap** — Sprint 0 (P0–P4), pas encore en production.

État détaillé bot par bot : [`docs/ARGOS_OPS_PLAN.md` — Annexe D](docs/ARGOS_OPS_PLAN.md#annexe-d--catalogue-cible--12-services--79-bots).

---

## Quickstart (à venir)

```bash
git clone git@github.com:Omnividens-argos/argos-ops.git
cd argos-ops
uv sync
cp .env.example .env.local
# remplir .env.local avec vos secrets
uv run pytest
```

---

## Documentation

- [`CLAUDE.md`](CLAUDE.md) — instructions Claude Code
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — architecture technique
- [`docs/AGENTS_PLAYBOOK.md`](docs/AGENTS_PLAYBOOK.md) — détail des 12 agents
- [`docs/ESCALATION_RULES.md`](docs/ESCALATION_RULES.md) — règles Tier 0-4
- [`docs/COMPLIANCE.md`](docs/COMPLIANCE.md) — RGPD / AI Act
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — journal des décisions

---

## Licence

Propriétaire — Omnividens. Tous droits réservés.
