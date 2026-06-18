---
id: rgpd-registry
role: compliance
references: run-rgpd-audit
guardrails: [deterministe, conservateur, garde-fou-bloquant, humain-prioritaire]
---

Tient et valide le registre RGPD des traitements (`compliance.load_rgpd_registry`)
: chaque traitement PII doit déclarer une base légale parmi les 6 de l'art. 6, une
finalité, les données collectées, la durée de conservation, et être revu < 12 mois.
Tout manque = gap. **Garde-fou bloquant (« Python tranche »)** : un gap (ou un
registre absent) gèle l'onboarding d'un nouveau traitement (facturer un nouveau
client) — le cerveau ne peut jamais lever ce gel. Déterministe, conservateur.
