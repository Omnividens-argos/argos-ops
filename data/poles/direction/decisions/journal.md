## D-001 — Architecture v2 pôle / agent / script
**Date :** 2026-06-17
**Partie :** S0
**Décision :** Refondre Argos Ops en 8 pôles métier, chacun avec un agent (cerveau LLM) et des scripts (bras déterministes) qui écrivent leur propre mémoire fichier.
**Pourquoi :** Découpler la décision (agent) de l'exécution (script) et donner à chaque pôle une mémoire locale auditable, sans dépendance DB.
**Implication technique :** BaseScript + BaseAgent + mémoire 1 fait = 1 fichier sous data/poles/<pole>/scripts/<script>/memory/.

---

## D-002 — Direction = pôle transversal avec gel de publication
**Date :** 2026-06-18
**Partie :** S6
**Décision :** Le pôle Direction lit la mémoire de toute la flotte et gèle la publication d'artefacts publics (release notes / changelog / roadmap) tant qu'un bug P0 est ouvert ou qu'un pôle est en santé critique.
**Pourquoi :** Donner à la Direction un garde-fou « Python tranche » homogène avec les autres pôles (Bloctel Vente, conformité Finance, breaker Pub) : on ne communique pas vers l'extérieur pendant une régression critique.
**Action de suivi :** Brancher la synthèse cerveau (claude -p) sur le fallback heuristique en S+.

---

## D-003 — Board pack & roadmap local-first (snapshots fichiers)
**Date :** 2026-06-18
**Partie :** S6
**Décision :** Les KPIs board pack (MRR/burn/runway/NRR) viennent d'un snapshot data/poles/direction/board/metrics.yaml et le changelog d'un snapshot de commits — aucun appel Stripe / git en lecture cockpit.
**Pourquoi :** Cohérence D-017 (local-first, aucune API tierce, cockpit déterministe et testable offline).
