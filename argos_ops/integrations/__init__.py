"""Intégrations API externes : Stripe, Zimbra, Umami (analytics self-host).

Note D-017 : aucune intégration LLM tierce (Gemini, OpenAI, Voyage, etc.).
Tous les agents IA passent par Claude Code Pro Max (abonnement fondateur),
les embeddings KB par fastembed local. Umami (INFRA-02) est self-hosté →
analytics 100 % local, pas de SaaS.
"""
