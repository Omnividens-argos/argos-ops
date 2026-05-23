"""Marketing & Growth — helpers partagés entre les bots Sprint 12.

Modules :

- :mod:`argos_ops.marketing.trends` — lecture des sujets cyber tendance
  agrégés depuis ``data/trends/sources.yaml`` (alimenté manuellement
  pour l'instant, futur scraper)
- :mod:`argos_ops.marketing.analytics` — wrappers de lecture des
  métriques d'engagement (LinkedIn / Mastodon) depuis le fichier
  ``data/social/engagement.yaml``
"""

from __future__ import annotations

from argos_ops.marketing.analytics import EngagementMetrics, load_engagement_window
from argos_ops.marketing.trends import TrendItem, load_trend_sources, score_trends

__all__ = [
    "EngagementMetrics",
    "TrendItem",
    "load_engagement_window",
    "load_trend_sources",
    "score_trends",
]
