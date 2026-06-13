"""Sous-package ``_watchdog`` — logique pure des 4 sous-analyses fusionnées
dans :class:`argos_ops.agents.fleet_watchdog.FleetWatchdog` (Axe 3.2).

Chaque module conserve la logique déterministe (collecte + report + embed)
d'un ancien watcher autonome, désormais orchestrée en **une seule passe**
par FleetWatchdog (1 lecture ``agent_runs``, 1 embed multi-sections, 1 cron) :

- :mod:`health`  — freshness / uptime par agent + breakers (ex-``BotHealthBot``)
- :mod:`perf`    — latence P50/P95 + taux d'erreur (ex-``BotPerfAnalyzer``)
- :mod:`errors`  — clustering par signature d'exception (ex-``ErrorTriageBot``)
- :mod:`anomaly` — pic de volume d'erreurs (ex-``LogAnomalyDetector``)

Les fonctions pures (``collect_*`` / ``build_report`` / ``classify`` /
``extract_signature``) sont conservées à l'identique pour préserver la
couverture de tests existante (cf. ``tests/test_bot_health.py`` &c.).
"""
