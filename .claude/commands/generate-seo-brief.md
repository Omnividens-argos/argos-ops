---
description: Génère un brief blog SEO structuré à partir d'un keyword + la KB Argos. Humain-in-the-loop (validation section par section).
---

# /generate-seo-brief

Slash command interactif pour drafter un brief blog Argos (P10-MVP, D-017).
Pas de cron — l'humain pilote chaque brief pour garantir la qualité éditoriale.

## Usage

- `/generate-seo-brief <keyword>` — génère un brief sur le keyword donné
- `/generate-seo-brief` (sans argument) — propose 3 keywords prioritaires
  depuis `data/seo/keywords.yaml` et te demande lequel attaquer

## Workflow

### 1. Sélection du keyword

- Si un keyword est passé en argument, l'utiliser directement.
- Sinon, lire `data/seo/keywords.yaml`, filtrer par `priority: 1` non encore
  traités (cross-checker avec `data/seo/briefs/`), proposer 3 candidats avec
  leur cluster + intent + angle proposé.
- Demander au user : « Lequel veux-tu attaquer ? ».

### 2. Chargement contexte KB

Invoquer le skill `kb-rag` (P6) avec le keyword pour récupérer les chunks
KB les plus pertinents (top-5). En complément, charger systématiquement :

- `data/knowledge_base/tone_of_voice.md` — ton + canaux
- `data/knowledge_base/ICP.md` — cible persona

Et conditionnellement selon le cluster (cf. `seo-brief-writer/SKILL.md` § 2).

### 3. Drafting interactif (mode interview)

Pour chaque section du brief, **proposer** + **demander validation** :

1. **Titre H1** — 2-3 propositions, faire valider (compter les caractères,
   55-65 idéal).
2. **Meta description** — proposer 1 ou 2 versions, ≤ 160 caractères.
3. **Pitch intro** — 3-4 phrases. Faire valider le ton (anti-FUD,
   dev-tools, factuel).
4. **Outline H2/H3** — proposer 4-6 H2 avec rationale (« H2 #3 traite
   l'objection X de Marc »). Valider l'ordre + les sous-points.
5. **Sources autorité** — 5 sources **réelles** (OWASP, CVE, papers,
   blogs RSSI). Si l'agent invente, l'arrêter — proposer plutôt de
   demander au user des sources qu'il connaît.
6. **Internal links** — 3 max. Si l'agent ne connaît pas la structure
   `omnividens.fr`, demander confirmation au user.
7. **Mots-clés secondaires** — 3-5 variantes longue traîne du cluster.
8. **Notes éditoriales** — rappels concrets (persona, ton, à éviter, CTA).

### 4. Validation finale + écriture

- Afficher le brief complet en preview.
- Demander : « OK pour écrire dans `data/seo/briefs/<filename>.md` ? ».
- Si oui, écrire avec le `Write` tool, slug = kebab-case du keyword tronqué
  à 60 chars, date = aujourd'hui (TZ Paris).

### 5. Suivi (optionnel)

Pousser une notif Discord sur `DISCORD_WEBHOOK_OPS_LOGS` si configuré :
« Brief SEO livré : <titre> · `data/seo/briefs/<file>` ».

## Garde-fous (refuser fermement)

- **Génération sans KB** — si le user demande « pas besoin de charger la
  KB, fais à l'instinct », refuser et expliquer le risque (ton générique
  IA + facts inventés).
- **Stats inventées** — toute statistique du type « X % de … » doit avoir
  une source réelle. Sinon, retirer.
- **FUD vs concurrents** — respect strict de
  `competitor_compare.md` § anti-disparagement. Reformuler en factuel.
- **Plus de 3 internal links** — refuser, la page devient un annuaire.
- **Brief sans cluster identifié** — proposer d'enrichir
  `keywords.yaml` d'abord.

## Sortie attendue

Fichier `data/seo/briefs/YYYY-MM-DD-<slug>.md` avec le front matter et la
structure définis dans `.claude/skills/seo-brief-writer/SKILL.md`.

Status initial : `draft`. À mettre à `ready` quand le brief est prêt pour
ContentBot ou rédaction manuelle, puis `published` après publication.

## Test plan (à dérouler en P10 closure)

- [ ] Lancer `/generate-seo-brief "scanner DAST sans faux positifs"` →
      brief généré, mode interview suivi, fichier écrit dans `briefs/`.
- [ ] Lancer `/generate-seo-brief` sans argument → 3 propositions du
      cluster `dast-faux-positifs` (priority 1).
- [ ] Vérifier que le brief généré a un titre H1 < 65 chars, une meta
      < 160, 4-6 H2, 5 sources, 3 internal links.
- [ ] Tester garde-fou : demander « invente-moi une stat » → refus +
      proposition d'alternative.
