# Argos Ops — SEO (P10)

> Stratégie keywords + briefs générés pour ContentBot (P9 futur).
> Documentation `docs/ARGOS_OPS_PLAN.md` § 10 + décision option A 2026-05-12.

## Structure

- `keywords.yaml` — liste seed des keywords cibles, groupés par cluster
  sémantique. Curé manuellement, à enrichir au fil des briefs produits.
- `briefs/` — briefs markdown générés par le slash command
  `/generate-seo-brief`. Nommage : `YYYY-MM-DD-<slug-keyword>.md`.

## Workflow P10-MVP (D-017)

1. **Préparer la cible** — choisir un keyword dans `keywords.yaml` (priorité 1
   d'abord). Vérifier qu'il n'y a pas déjà un brief dans `briefs/`.
2. **Générer le brief** — invoquer `/generate-seo-brief <keyword>` dans
   Claude Code. Le slash command :
   - Charge le contexte KB pertinent (via `kb-rag` P6) — features Argos,
     pricing, ton, comparatif concurrence.
   - Génère un brief markdown structuré (titre, outline H2/H3, sources,
     internal links, meta).
   - Te demande de valider section par section (mode interview, comme P3-M2).
3. **Sauvegarder** — le brief validé est écrit dans
   `briefs/YYYY-MM-DD-<slug>.md` par Claude Code, prêt pour ContentBot ou
   pour rédaction manuelle.
4. **Itérer** — ajoute le keyword traité dans une section « done » de
   `keywords.yaml` ou suivre via git history.

## Cadence

- **Hebdo** : 1-2 briefs / semaine (cf. plan P10).
- **Pas de cron** en P10-MVP — c'est un slash command interactif comme
  `/check-emails` (D-017 humain-in-the-loop pour qualité éditoriale).

## Évolutions futures

- **P10.1 — SERP analyzer** : ajouter scraping Google SERP pour identifier
  les keyword gaps réels vs concurrence. Hors scope P10-MVP (cf. décision
  2026-05-12 : risque IP ban + KB Argos suffit pour démarrer).
- **P9 — ContentBot** : consommera ces briefs pour publier sur le blog
  (Ghost/WordPress headless), LinkedIn (P11), Mastodon (P11). Reddit
  retiré du périmètre par [D-022](../../docs/DECISIONS.md#d-022--retrait-d%C3%A9finitif-de-reddit-du-p%C3%A9rim%C3%A8tre-argos-ops).
- **Google Search Console** : croiser les positions réelles avec les
  keywords du fichier — déclenche révision des priorités.

## Anti-patterns à éviter

- **Génération IA pure sans KB** — produit du contenu générique. Toujours
  charger la KB via `kb-rag` avant de drafter.
- **Faux exemples chiffrés** — pas de stats inventées (« 87 % des RSSI
  pensent que… »). Citer des sources réelles ou ne pas chiffrer.
- **Comparatifs anti-concurrents** — respecter § anti-disparagement de
  `competitor_compare.md`. Comparer factuellement, pas dénigrer.
- **Trop d'articles sur un même cluster** — diversifier les clusters pour
  capter plus de longue traîne plutôt que cannibaliser.
