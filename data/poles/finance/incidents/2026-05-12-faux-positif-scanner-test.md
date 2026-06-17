---
title: Faux positif scanner sur un client test
date: 2026-05-12
category: misconfig
severity: P2
status: resolved
reporter: founder
---

# Post-mortem — Faux positif scanner sur un client test

## Résumé en 1 ligne

> Le scanner Argos a remonté une CVE critique inexistante (signature mal versionnée)
> sur l'environnement de démo d'un prospect.

## Impact

- Utilisateurs touchés : 1 (compte démo)
- Données touchées : aucune
- Durée totale : 2 h
- Notification CNIL requise (>72h, RGPD art. 33) : non

## Cause racine

Base de signatures non rechargée après un déploiement à chaud.

## Lessons learned

Recharger systématiquement la base de signatures dans le healthcheck post-deploy.
