-- Argos Ops — Migration IN/OUT par run (cockpit BotDetail onglet Travail)
-- Ajoute la capture structurée de ce qu'un agent a regardé (inputs) → produit
-- (outputs) sur chaque ligne agent_runs. Renseigné par l'agent via
-- RunResult.inputs / RunResult.outputs (cf. argos_ops.agents.base.IOItem).
-- Idempotente : ré-application sans casser un schéma déjà migré.

BEGIN;

-- Liste JSON d'IOItem {label, kind, detail, ref, count}. NULL = bot non
-- instrumenté → l'UI cockpit retombe sur une vue dérivée (output_summary +
-- drafts + mémoire). Pas d'index : lecture toujours par run_id / agent_name.
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS inputs  JSONB;
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS outputs JSONB;

COMMIT;
