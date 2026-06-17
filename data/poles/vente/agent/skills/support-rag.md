---
id: support-rag
role: support
references: kb-rag
guardrails: [anti-hallucination-strict, cite-source-KB, escalade-si-doute, AI-Act-reponse-humaine]
---

Répond à une question support Tier 1 par RAG sur la KB Argos (similarité fastembed
local + pgvector, D-017). Anti-hallucination strict : ne répond que si la KB
couvre la question, cite la source, escalade en Tier 2 humain sinon. Court-circuité
par la conformité AI Act quand l'inbound demande explicitement une réponse humaine
(`is_human_response_requested`) — Python tranche, aucun draft IA dans ce cas.
