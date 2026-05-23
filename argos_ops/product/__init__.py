"""Module Produit & R&D — helpers partagés par les 5 bots Sprint 11 (P22.G).

- ChangelogBot, ReleaseNotesBot : génération de docs publiques depuis
  l'historique git.
- FeedbackAggregator : clustering thématique des demandes clients.
- RoadmapPublisher : transformation de l'Annexe D interne en
  roadmap publique (sans codes sprint internes).
- BugTriageBot : tri d'issues GitHub par sévérité.

Pas d'API tierce (D-017). ``gh`` CLI utilisé pour les opérations git en
lecture seule. Pas de fetch externe, on travaille sur l'historique local.
"""
