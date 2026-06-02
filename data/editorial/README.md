# `data/editorial/`

Queue de recommandations éditoriales produite par **EditorialBot**
(`/run-editorial`).

## Workflow

1. **TrendSpotter** (`/run-trend-spot`) écrit `data/trends/digest-<date>.md`
   (top-5 sujets cyber chauds).
2. **EditorialBot** (`/run-editorial`) lit le dernier digest et écrit
   `queue-<date>.yaml` : pour chaque sujet, un **canal + writer + angle**
   recommandés.
3. Le **fondateur** ouvre la queue et lance manuellement les `/draft-*`
   listés (humain-in-the-loop, audit `claude-judge` à chaque draft).

EditorialBot **ne drafte rien lui-même** (mode shadow) : il oriente.

## Format `queue-<date>.yaml`

```yaml
generated_at: "2026-06-02T08:00:00+00:00"
source_digest: digest-2026-06-02.md
mode: shadow
tasks:
  - topic: "Faille critique sur Ivanti EPM"
    channel: linkedin
    writer: linkedin-writer
    slash: /draft-linkedin
    angle: "Angle décideur : relier le sujet à une objection RSSI/CTO, CTA soft."
```

## Répartition des canaux

| Type de sujet | Canal | Writer |
|---|---|---|
| Grand public (phishing, ransomware, mot de passe…) | Meta | `meta-writer` |
| Autres (cyber / technique / décideur) | round-robin LinkedIn → Mastodon → Bluesky → X | writer du canal |
| — | ~~Truth Social~~ exclu (expérimental + brand safety apolitique) | — |

## Statut des fichiers

Les `queue-<date>.yaml` sont des **sorties générées** (non commitées,
gitignorées). Seul ce README est suivi en git.
