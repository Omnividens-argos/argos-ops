"""Agents Argos Ops — slash commands Claude Code orchestrés via cron.

Chaque agent hérite de :class:`argos_ops.agents.base.BaseAgent` et implémente
``async def run(self) -> RunResult``. L'orchestration (cron, breaker check,
log agent_runs) est partagée par :func:`run_agent` du module ``base``.

Cf. D-017 : tous les agents tournent sur l'ordi du fondateur (Task
Scheduler / cron WSL2), pas sur le serveur SecHunter.
"""
