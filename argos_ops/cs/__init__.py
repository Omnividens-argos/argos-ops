"""Module Customer Success — modèles, scoring, loaders, templates partagés.

Consommé par les 8 bots CS de Sprint 7 (P22.G) :
- OnboardingBot, NPSCollector, ReviewBot : drafts email humain-in-the-loop
- HealthScoreBot, UpsellSpotter, ChurnPredictor : scoring read-only
- KBUpdater : détection gaps KB depuis tickets
- EscalationRouter : tri tickets par priorité + SLA

Toutes les données client sont saisies à la main par le fondateur dans
``data/cs/customers.yaml`` (D-017 — pas d'API tierce). Les tickets dans
``data/support/tickets.yaml``.
"""
