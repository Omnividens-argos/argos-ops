---
title: Clé API exposée dans un log de test
date: 2026-06-15
category: data_leak
severity: P1
status: open
reporter: founder
---

# Post-mortem — Clé API exposée dans un log de test

## Résumé en 1 ligne

> Une clé API de test (compte sandbox) a été imprimée en clair dans un log local
> avant que le filtre loguru anti-fuite ne soit appliqué au nouveau module.

## Impact

- Utilisateurs touchés : 0 (clé sandbox, non production)
- Données touchées : aucune donnée client
- Durée totale : en cours
- Notification CNIL requise (>72h, RGPD art. 33) : non (pas de PII)

## Cause racine

> _À compléter — le nouveau module n'était pas couvert par le filtre loguru._

## Actions correctives (court terme)

- [ ] Rotater la clé sandbox exposée
- [ ] Étendre le filtre loguru au module concerné
