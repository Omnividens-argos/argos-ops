# Argos — FAQ

> **Source de vérité** des Q&R récurrentes pour SupportBot, OutboundBot
> et la page `/faq` publique. Si une autre source répond
> différemment à une question listée ici, **ce fichier prime** — créer
> une PR pour aligner.
>
> Source : interview fondateur en P3-M2 (2026-05-08), croisée avec
> [`pricing.md`](pricing.md), [`argos_features.md`](argos_features.md),
> [`competitor_compare.md`](competitor_compare.md),
> [`tone_of_voice.md`](tone_of_voice.md), et les décisions D-010 à D-016
> dans [`DECISIONS.md`](../../docs/DECISIONS.md).
>
> Ton (cf. [`tone_of_voice.md` § 5](tone_of_voice.md#5-tutoiement--vouvoiement)) :
> tutoiement par défaut sur signup / dashboard / support technique.
> Le « tu » qu'on emploie ici est cohérent avec le canal premier d'usage
> (dashboard + emails support entrants) ; SupportBot adapte au canal réel
> (vous sur mail facture / légal).

---

## 1. Pricing & licensing

### « C'est combien ? »

4 plans + 1 carte « Custom contact » discrète :

- **Free** — 0 €/mois, 41 modules sévérité ≤ HIGH (CRITICAL masqués)
- **Pro** — 39 €/mois HT, 139 modules, 1 user, 70 scans/jour
- **Team** — 129 €/mois HT, 139 modules, 3 users, 250 scans/jour
- **Pro Max** — 249 €/mois HT, 139 modules, 10 users, scans illimités

**Annuel = -20 %** (~2,4 mois offerts), payé en une fois à la
souscription. Tous les tiers payants incluent **les 139 modules**, la
différence c'est le quota de scans, le nombre de seats, le Watch
(Pro Max only) et le support SLA.

Tu peux signer en self-serve depuis
[omnividens.fr/pricing](https://omnividens.fr/pricing). Pour un Custom
contact (≥ 5 000 €/mois — SLA contractuel, MSA, data residency garantie)
contacte `contact@omnividens.fr`.

→ Détails complets : [`pricing.md`](pricing.md).

### « Pourquoi pas par cible scannée comme Acunetix ? »

Notre quota est en **scans par jour**, pas par cible enregistrée. Tu
peux scanner autant de domaines, IP ou repos différents que tu veux
dans ton quota quotidien. Marc qui a 5 sous-domaines paie le même prix
Team que Marc qui en a 2.

→ Cf. [`pricing.md` § 3](pricing.md#3-unit%C3%A9-de-facturation--scansjour-pas-par-cible).

### « C'est quoi la différence Team vs Pro Max ? »

Team (129 €) couvre les besoins d'une équipe scaleup classique : 250
scans/jour, 3 seats, CI/CD intégré, rapports clean. Pro Max (249 €)
rajoute le **Watch** (re-scan continu hebdo avec notif des nouveaux
findings), le **white-label complet**, **l'IA fallback auto** (bascule
auto entre tes BYOK configurés en cas de rate-limit), 10 seats, et le
support Slack dédié < 8 h.

Si tu es une fintech / healthtech qui prépare une certif (SOC2, ISO,
HDS), Pro Max est fait pour toi.

→ Cf. [`pricing.md` § 2](pricing.md#2-d%C3%A9tail-des-fonctionnalit%C3%A9s-par-tier).

### « Vous avez un Enterprise ? »

Pas de plan Enterprise public au launch. Si tu as besoin d'un SLA
contractuel, d'un MSA, ou de data residency EU stricte, on fait du
**Custom à partir de 5 000 €/mois**. Écris à `contact@omnividens.fr`
avec tes besoins, on revient sous 48 h.

### « Vous remboursez ? »

**14 jours sans condition**, peu importe le motif. Tu cliques annuler
dans ton compte ou tu m'écris à `contact@omnividens.fr`, je rembourse.
Au-delà : pas de remboursement automatique mais cas par cas si abus
manifeste de notre côté (bug bloquant, downtime).

→ Cf. [`pricing.md` § 7](pricing.md#7-refund--cancellation--downgrade).

### « J'ai dépassé mon quota Pro / Team. Je peux acheter du hors-quota ? »

**Non sur Pro et Team** — tu es rate-limité jusqu'à minuit J+1, et
l'UI te propose l'**upgrade au tier supérieur** (cf.
[D-010](../../docs/DECISIONS.md#d-010--add-on--scans-hors-quota--r%C3%A9serv%C3%A9-au-tier-free)).
Pro Max est illimité par design, pas concerné. **Le hors-quota à
19 €/scan est réservé au Free**, c'est une transition vers Pro.

Si tu hit régulièrement ton quota Pro (70 scans/jour) ou Team (250),
le bon move est l'upgrade. C'est moins cher au scan que le hors-quota.

### « J'étais Pro à 30 €/mois avant la refonte v2. Qu'est-ce qui change ? »

**Rien.** Tu gardes ton tarif legacy via le `price_id` Stripe historique
reconnu par notre webhook. Pas de migration forcée. Si tu veux
volontairement basculer vers la nouvelle grille (ex : pour passer en
Team 129 €), tu cliques « changer de plan » et tu bascules sur la
grille v2.

→ Cf. [`pricing.md` § 1](pricing.md#politique-grandfather-d%C3%A9j%C3%A0-cod%C3%A9e).

### « Vous facturez en HT ou TTC ? Vous gérez la TVA UE ? »

**HT par défaut** sur la page Pricing (« TVA en sus » mention claire).
**Stripe Tax activé** : auto-collecte TVA UE selon pays de facturation,
gestion automatique du reverse charge B2B intra-UE pour les boîtes avec
VAT ID valide. Particuliers / freelance UE sans VAT ID → TVA française
20 % appliquée d'office. Hors-UE (US, UK post-Brexit, Asie) : pas de
TVA collectée par défaut au launch.

→ Cf. [`pricing.md` § 9](pricing.md#9-devises-tva-stripe-tax).

---

## 2. Onboarding & première utilisation

### « Comment je connecte mon premier domaine ? »

Pas de « connexion » — Argos est un **scanner externe**. Tu colles
l'URL / domaine / IP / CIDR / chemin code dans le wizard étape 1 du
dashboard, le type est auto-détecté. Pour des cibles authentifiées
(zone admin), tu fournis une **recipe d'auth en JSON** dans le
credentials vault (ou flag CLI `--auth-recipe`).

Le wizard a 3 étapes :
1. **Cible** — auto-détection URL/IP/domain/CIDR/code
2. **Focus** — 7 profils prédéfinis ou modules custom
3. **Lancement** — modèle IA, mode aggressive, credentials vault

### « Pourquoi mon scan dure-t-il 30 minutes ? »

C'est normal. Argos exécute jusqu'à 139 modules en parallèle avec
rate-limiting adaptatif (Cloudflare-aware). Découpage typique :

- **Phase 0 (intel)** — ~10 s
- **Phase 1-2 (modules web/network)** — 2-30 min selon agressivité
- **Phase 3-4 (IA-corrélation + enrichment)** — 30 s à 2 min

Tu peux lancer en background, on t'envoie un email/webhook quand c'est
fini. Un scan « full pentest » peut atteindre 45 min sur cible large.

### « Comment je vois mon premier finding ? »

Pendant le scan, le dashboard affiche la progression temps réel
(websocket `/api/ws/scan/{id}`). Une fois fini : page Scan Detail avec
findings groupés par sévérité + chaînes d'attaque IA + risk score A-F
(cf. [`argos_features.md` § 4.5](argos_features.md#45-risk-score-a-f-d%C3%A9terministe)).

Tu peux aussi exporter en MD / HTML / PDF / SARIF (selon tier — Free
limité à MD + PDF watermark, Pro+ ajoute SARIF / JSON / HTML).

### « Mon scan a échoué, pourquoi ? »

3 causes typiques :

1. **Cible derrière captcha / auth** → fournir une auth-recipe (vault
   ou flag `--auth-recipe`)
2. **Timeout 120 s par module dépassé** sur cible très lente → relancer
   avec `--aggressive=false`
3. **WAF strict (Cloudflare)** → Argos détecte automatiquement et adapte
   concurrence / délai (cf. ORCH-01 dans le code)

Si aucune des 3 ne colle, ouvre un ticket support avec le `scan_id` —
on regarde dans les logs.

### « Je veux scanner 10 cibles d'un coup, comment ? »

**Free n'a pas de batch** (1 cible / scan). Pro 5/batch, Team 20/batch,
Pro Max 50/batch.

- Via CLI : `argos scan --target a.com --target b.com ...`
- Via API : `POST /api/scans` avec liste de targets

→ Cf. [`pricing.md` § 2](pricing.md#2-d%C3%A9tail-des-fonctionnalit%C3%A9s-par-tier)
pour la table des limites par tier.

---

## 3. Sécurité & confidentialité

### « Où sont stockées mes données ? »

**Hébergement européen (UE)** — VPS Hetzner / OVH / DigitalOcean en
France / Allemagne / Pays-Bas selon la croissance et la zone du
client. Pour confirmer la région exacte applicable à ton compte
(important pour data residency contractuelle), contacte
`contact@omnividens.fr`.

Les Custom contact (≥ 5 000 €/mois) peuvent obtenir une **garantie
contractuelle de data residency EU stricte** dans le MSA.

### « Vous chiffrez mes données ? »

**Oui — AES-256-GCM** sur les données sensibles :

- **Clés API user (BYOK)** chiffrées avec `crypto_service.py` (master
  key 32 bytes via env `SECHUNTER_ENCRYPTION_KEY`)
- **Mot de passe SMTP** chiffré pour les notifications outbound
- **Sessions admin** : tokens JWT signés en HMAC-SHA256

Les findings (résultats de scan) ne sont **pas chiffrés en base** —
c'est de la donnée que tu produis, pas un secret tiers. Si tu veux
data-at-rest encryption complète sur la DB, c'est partie du Custom
contact (LUKS sur le serveur dédié).

### « Vous gardez mes findings combien de temps ? »

**Rétention minimale garantie par tier** (cf.
[D-016](../../docs/DECISIONS.md#d-016--r%C3%A9tention-findings--promesse-minimale-tenue-purge-automatique-en-roadmap)) :

- **Free** — 30 jours
- **Pro** — 90 jours
- **Team** — 1 an
- **Pro Max** — illimité

En pratique aujourd'hui, les findings sont conservés **au-delà** de
cette durée minimale — la purge automatique en cron est sur la roadmap
technique. **Si tu veux purger immédiatement** : `Account → Delete
scan` (par scan) ou `Account → Delete data` (suppression complète
RGPD).

Note : les **PDF déjà générés** restent téléchargeables 12 mois depuis
l'URL initiale, même après purge des findings.

### « Vous êtes SOC2 / ISO 27001 certifiés ? »

**Pas au launch.** SOC2 Type 2 est sur la roadmap (target 2027), ISO
27001 derrière. Aujourd'hui Argos opère en **self-claim RGPD-compliant**
avec les mécanismes implémentés (droit à l'oubli, encryption at rest
sur secrets, BYOK pour les clés tierces).

Si la certification est **un blocker contractuel** pour ton organisation
(audit fournisseurs strict), on peut le discuter en Custom contact —
mais les certifs prendront 12-24 mois minimum, donc ce n'est pas
livrable pour un signing imminent.

### « Comment je supprime toutes mes données (RGPD droit à l'oubli) ? »

Route `DELETE /api/user/account` (visible dans Settings → Danger zone).
**Soft delete + anonymisation** : ton user est anonymisé, les clés API
sont supprimées en cascade, les scans restent en DB associés à l'ID
anonyme (intégrité technique).

Confirmation requise (saisie « SUPPRIMER » dans la modale). Effet
immédiat. Si tu veux un certificat de suppression écrit pour ton DPO,
demande à `contact@omnividens.fr`.

### « Mes scans peuvent toucher des sites tiers — c'est légal ? »

**Tu es responsable des autorisations** sur les cibles que tu scannes.
Argos scanne ce que tu lui dis de scanner. Tu dois t'assurer d'avoir le
droit légal (CGU du site cible, autorisation écrite, propriété de la
ressource, scope bug bounty officiel).

Argos n'est **pas un outil pour scanner des cibles non-consentantes**
(cf. [`tone_of_voice.md` § 9](tone_of_voice.md#9-convention-placeholders-pour-les-exemples-publics)
qui dit pourquoi on ne cite jamais de domaines réels en exemple). En
cas d'usage abusif, on peut suspendre le compte.

---

## 4. Couverture & modules

### « Combien de modules vous avez ? »

**139 modules** sur 6 catégories :

| Catégorie | Modules |
|---|---:|
| web (DAST) | 49 |
| network | 31 |
| recon | 20 |
| sast | 14 |
| api | 13 |
| cloud | 12 |

Free a accès à **41 modules** (sévérité max ≤ HIGH). Tous les tiers
payants ont les 139.

→ Catalogue exhaustif : [`argos_features.md` § 2](argos_features.md#2-catalogue-exhaustif-139-modules).

### « Vous faites du SAST ? »

Oui, mais en **complément**, pas en cœur de métier. **14 modules sur
139 (~10 %)** — wrappers fins autour de tree-sitter, ruff, semgrep,
trufflehog, hadolint, checkov. Couverture : Python, JS/TS, Java, C#,
PHP, Go, Ruby, secrets multi-langage, dépendances (CVE via OSV.dev),
supply-chain, Docker, IaC (Terraform, CloudFormation, K8s, Helm).

Pour du SAST profond avec licence policy enforcement et patch
suggestion auto-PR, **on redirige vers Snyk Pro** — ce n'est pas notre
métier (cf. [`argos_features.md` § 5.3 antimatière](argos_features.md#53-pas-de-sca-full-%C3%A9cosyst%C3%A8me-snyk--dependabot-grade)).

### « Vous faites du mobile (iOS / Android) ? »

**Non.** Pas de module mobile, pas de scan APK / IPA, pas de runtime
mobile (Frida, Objection). Choix produit délibéré.

Pour du mobile, on redirige vers **MobSF** (open-source), **NowSecure**,
**Appknox**, **Veracode Mobile** ou un consultant **OWASP MASVS**.

→ Cf. [`argos_features.md` § 5.4 antimatière](argos_features.md#54-pas-de-mobile-masa--ios--android).

### « Vous faites du BAS / Breach Attack Simulation ? »

**Non.** Argos est un scanner **externe** (DAST + SAST + cloud) qui
cherche les vulns exploitables. La simulation adversariale interne
(SafeBreach, AttackIQ, Cymulate, Pentera) est un autre métier
(exécution de payloads dans des environnements contrôlés, intégration
EDR, scoring MITRE temps réel).

Pour du BAS : **Pentera**, **SafeBreach**, **AttackIQ**, **Cymulate**
(segment enterprise) ou **Atomic Red Team** (open source).

→ Cf. [`argos_features.md` § 5.1 antimatière](argos_features.md#51-pas-de-bas--breach-attack-simulation).

### « C'est quoi la différence entre Watch et Chaînes d'attaque ? »

Souvent confondus. Réponse canonique
([D-012](../../docs/DECISIONS.md#d-012--d%C3%A9finitions-canoniques-watch-et-cha%C3%AEnes-dattaque-kb)) :

| | Chaînes d'attaque | Watch |
|---|---|---|
| **Quand** | Pendant chaque scan (à la fin) | Entre les scans (re-scan auto) |
| **Quoi** | Corréler les findings d'un seul scan en kill chain narratif | Comparer les findings sur plusieurs scans dans le temps |
| **Tier** | Pro / Team / Pro Max | Pro Max uniquement |
| **Sortie** | Section dans le rapport courant | Timeline + alertes Slack/email |

→ Détail complet : [`argos_features.md` § 4.3](argos_features.md#43-cha%C3%AEnes-dattaque-correlator)
et [§ 4.4](argos_features.md#44-watch--surveillance-continue-pro-max-only).

### « Vous trouvez du 0-day ? »

Pas notre promesse principale. Argos couvre les 139 vulns connues +
patterns de misconfig + dépendances CVE via OSV.dev. Pour la chasse
au 0-day, **Detectify Crowdsource** a un meilleur edge (chercheurs
incentivés à creuser tôt sur les CVE émergentes) — mais à 800 €/mois
avec une latence de discovery → CVE → module.

Argos sort du « semi-0-day » via les **chaînes d'attaque IA** (un
finding LOW + un finding MEDIUM peuvent former une chaîne CRITICAL
qu'aucun scanner ne flague isolément), ce qui est sa valeur ajoutée
réelle.

### « Vous scannez les API GraphQL ? »

**Oui** — module `api.graphql_injection` qui couvre **6 catégories
d'injection × 3 locations × 4 oracles**. SQLi, NoSQLi, RCE command,
RCE SSTI, LDAPi, XPathi en argument inline / variable GraphQL /
directive `@skip-@include`.

Whitelist Shopify Storefront pour éviter les FP sur les API GraphQL
publiques. Aucun scanner DAST mainstream ne couvre cette matrice
complète.

→ Cf. [`argos_features.md` § 3.5](argos_features.md#35-api--3-zooms).

### « Quelle différence avec Acunetix / Detectify / Burp / Intruder ? »

Réponses détaillées par concurrent : voir
[`competitor_compare.md`](competitor_compare.md).

Résumé court :

- **Acunetix** : nous = 10× moins cher, formule risk score transparente,
  RGPD article-par-article. Eux = certif PCI-ASV, intégrations
  enterprise mature
- **Detectify** : nous = scanner maintenu industriel + IA-corrélation à
  39 €. Eux = communauté Crowdsource pour 0-day émergents
- **Burp Pro** : complémentaires — eux = manuel, nous = automatisé
- **Intruder** : nous = -22 % à -59 % avec 139 modules + IA-corrélation

---

## 5. IA & corrélation

### « Vous utilisez quelle IA ? »

Tu choisis. **BYOK multi-provider** : Anthropic Claude, OpenAI GPT,
Google Gemini, DeepSeek. Pas de lock-in vendor.

Tes clés sont chiffrées AES-256-GCM côté serveur, jamais loguées,
jamais exposées dans les rapports. **Aucun appel sortant ne part vers
une clé serveur Argos** (cf.
[D-011](../../docs/DECISIONS.md#d-011--ia-fallback-auto-pro-max--byok-seul-pas-de-cl%C3%A9-serveur-argos)).

→ Détails : [`argos_features.md` § 4.7](argos_features.md#47-byok-multi-provider-ia--fallback-automatique).

### « Et si je n'ai qu'une clé Anthropic, ça marche ? »

**Oui pour les scans simples.** Tous les rôles IA (Strategist, Analyst,
Correlator, Enricher, Reporter) peuvent tourner sur un seul provider.

**L'IA fallback auto (Pro Max only)** nécessite ≥ 2 providers
configurés pour basculer en cas de rate-limit (429) ou erreur 503. Si
tu n'en as qu'un et que ce provider échoue, le scan continue en mode
dégradé (findings sans corrélation IA / chaînes d'attaque).

Recommandation Pro Max : configure **Anthropic + OpenAI** dans
Settings → IA, le fallback prend le relais automatiquement.

### « Si tous mes providers échouent, qu'est-ce qui se passe ? »

Le scan **continue en mode dégradé** — les findings sortent quand
même (les modules de scan ne dépendent pas de l'IA), juste sans
corrélation IA, sans chaînes d'attaque, et sans enrichment de
remédiation par l'Enricher.

Le rapport final indique « IA corrélation indisponible — les findings
ci-dessous sont la sortie brute des modules ».

### « L'IA peut-elle envoyer mes données quelque part ? »

**Non.** Les appels IA partent depuis ton serveur Argos vers le
provider que **tu** as configuré, avec la clé que **tu** as fournie.
Argos n'a aucune télémétrie IA, aucune collecte centralisée des
prompts, aucune route OOB qui transite par notre infrastructure.

Pour les régulés (fintech / santé / défense) qui veulent garantie
contractuelle écrite : **Custom contact ≥ 5 000 €/mois** avec MSA.

### « Combien ça coûte de tokens IA par scan ? »

Très variable selon profil scan + cible :

- **Scan léger (5 modules, 1 cible petite)** : ~10-30 k tokens total
  (tous rôles IA confondus). Coût ~0,05-0,15 € chez Anthropic Sonnet
- **Scan full pentest (139 modules, 50 findings, chaînes corrélées)** :
  ~200-500 k tokens. Coût ~1-3 € chez Anthropic Sonnet, ~0,3-0,8 € chez
  Gemini Flash

Le **Correlator** est le rôle le plus tokenivore (raisonnement
long-context sur tous les findings ensemble). Argos active la **prompt
caching** chez Anthropic / OpenAI dès que le provider le supporte —
divise par 5-10× le coût sur les scans répétés (mêmes findings,
re-corrélation incremental).

---

## 6. Compliance & RGPD

### « Vous mappez les findings à PCI-DSS / RGPD / OWASP ? »

**Oui — triple framework :**

- **OWASP Top 10 2021** (clés `A01:2021` à `A10:2021`)
- **PCI-DSS 4.0** (refs : 1.2.1, 2.2.1, 3.4.1, 4.2.1, 6.2.4, 7.2.2,
  8.3.1, 10.2.1, 10.3.1, 11.3.1)
- **RGPD** (5 articles : 5(1)(f), 25, 32, 33, 34)

Sortie **factuelle** : count de findings par exigence violée, avec
liste des findings liés. **Pas de score % de couverture compliance**
(cf. [D-014](../../docs/DECISIONS.md#d-014--compliance-mapping-sortie-factuelle-count-par-exigence-pas-de-score--marketing))
— c'est délibéré, pour ne pas livrer un score arbitraire qu'un
auditeur exigerait de justifier ligne par ligne.

→ Détail : [`argos_features.md` § 4.6](argos_features.md#46-compliance-mapping-triple-framework).

### « Vous certifiez ma compliance PCI-DSS / RGPD / SOC2 ? »

**Non — Argos n'est pas un certificateur.** On vous fournit le
mapping factuel `finding → exigence violée` que votre auditeur
exigerait de toute façon. C'est plus rapide à contester ou à patcher
que les rapports compliance % de nos concurrents.

Pour la certification **officielle** (PCI-ASV, ISO 27001 audit,
SOC2 Type 2 attest), il faut un auditeur certifié — Argos peut être
ton outil de pré-audit pour réduire le scope, mais il ne signe pas
ton rapport ASV.

### « Le rapport Argos est-il utilisable directement par mon DPO ? »

Oui pour la partie technique. Le mapping RGPD article-par-article
(`Art. 32` majoritaire = sécurité du traitement, `Art. 33` =
notification violation, `Art. 34` = communication aux personnes
concernées) est sourcé au CWE et aux modules — un DPO peut consommer
le JSON directement.

Pour la partie **RoPA** (registre de traitements) et **AIPD**
(analyse d'impact), Argos ne livre pas — c'est un autre métier
(GRC). Si tu cherches une plateforme GRC : **OneTrust**, **Witik**
(FR), **Data Legal Drive**.

### « Vous gardez les logs de scan pour audit ? »

Oui — chaque scan a son `scan_id` UUID, son timestamp, son auteur,
ses paramètres et son résultat. Conservation : selon la rétention du
tier (cf. § 3 ci-dessus). Pour audit forensic ou litige client, le
log de scan est exportable en JSON sur demande à
`contact@omnividens.fr`.

---

## 7. Intégrations CI/CD & exports

### « Comment je branche Argos sur ma CI/CD ? »

3 voies possibles, toutes documentées dans le repo :

1. **CLI dans GitHub Actions / GitLab CI** — template prêt à coller
   (voir Q&R suivante)
2. **API REST** — `POST /api/scans` lance un scan, `POST
   /api/reports/{scan_id}/generate?format=sarif|pdf|html|markdown`
   génère le rapport. Auth via JWT bearer token
3. **Webhooks** sur `scan.completed` — Slack (Block Kit) / Discord
   (embeds) / Teams (adaptive cards) / generic. **Aujourd'hui dispo
   en CLI Watcher (`--webhook <url>`) ; configuration dashboard
   arrive en Pro+ roadmap T3 2026.**

→ Tier minimum CI/CD : **Pro** (les exports SARIF / CSV / JSON +
l'API REST sont gated Pro+).

### « Tu as un exemple de workflow GitHub Actions ? »

Validé contre le code, copier-coller direct :

```yaml
name: SecHunter Security Scan
on:
  workflow_dispatch:
    inputs:
      target:
        description: "Cible à scanner (URL, domaine, IP)"
        required: true
        type: string
  schedule:
    - cron: "0 2 * * 1"   # tous les lundis 2h UTC

jobs:
  scan:
    runs-on: ubuntu-latest
    permissions:
      security-events: write
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - uses: astral-sh/setup-uv@v4
      - run: uv sync
      - name: Run SecHunter scan
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          uv run python -m sechunter.cli scan \
            --target "${{ github.event.inputs.target || 'https://example.com' }}" \
            --format sarif \
            --output ./reports
      - uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: ./reports/
          category: sechunter
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: sechunter-reports
          path: ./reports/
          retention-days: 30
```

GitLab CI : équivalent simple via `image: python:3.12` + `uv run python
-m sechunter.cli scan` + upload artifact + intégration **GitLab Code
Quality** sur le SARIF.

### « Le SARIF est-il consommable par GitHub Code Scanning ? »

**Oui.** Le format SARIF v2.1.0 émis par Argos est validé contre le
schema GitHub. Une fois uploadé via `github/codeql-action/upload-sarif`,
les findings apparaissent dans **Security → Code scanning alerts** sur
ton repo, avec ouvert / fermé / dismissed status.

Triage CodeQL-style intégré : un finding peut être marqué
`dismissed: false-positive` côté GitHub, ce qui ne réinjecte pas le
finding au prochain push (mais c'est sur GitHub, pas dans Argos —
voir § 8 sur les FP).

### « Vous avez une intégration Slack / Discord / Teams native ? »

**Webhooks oui, intégration packagée non.**

- **Webhooks `scan.completed`** sortent en Block Kit (Slack), embeds
  (Discord), adaptive cards (Teams), ou generic JSON. Filtrage par
  sévérité min configurable
- **Configuration aujourd'hui** : via CLI Watcher (`--webhook <url>`)
  ou via API au moment du `POST /scans`. **Dashboard config user
  roadmap Pro+ T3 2026** (cf. D-016 sur les promesses tenues
  manuellement)

Pour des intégrations packagées (apps Slack natives avec OAuth, bot
mentions, slash commands), c'est sur la roadmap mais pas livré au
launch.

### « Et Jira / Linear / ServiceNow ? »

**Non au launch, intégrations packagées en roadmap.** Aujourd'hui la
voie pratique est :

1. **Webhook `scan.completed`** → endpoint custom qui crée les tickets
   Jira / Linear via leur API
2. Ou **export SARIF + GitHub** → conversion vers Jira via le plugin
   GitHub-Jira sync existant côté GitHub Marketplace

Si tu veux une intégration native packagée Argos → Jira / Linear avec
mapping champ-à-champ, c'est partie du **Custom contact ≥ 5 000 €/mois**
qui inclut un canal direct sur les priorités produit.

---

## 8. Faux positifs

### « Comment vous gérez les faux positifs ? »

Argos applique **3 niveaux de filtrage FP** (cf.
[D-015](../../docs/DECISIONS.md#d-015--faux-positifs--framing-tactique--3-niveaux--boucle-support--marquage-user-en-roadmap)) :

1. **Calibration des oracles au code** — 66 bugs FP corrigés en
   post-v2 (cf. `ARGOS_MODULE_BUGS.md` côté SecHunter). Pas une
   promesse marketing, du code mergé
2. **Q1-Q5 hardening** anti-bot, anti-SPA, anti-WordPress, whitelist
   placeholders, validation status-code sur chaque module. C'est ce
   qui tue les FP type « page WordPress qui retourne 200 HTML
   flaggée comme `.git/HEAD` exposé »
3. **Agent Analyst IA** qui score chaque finding (`confidence_score`
   0-1) et exclut automatiquement ceux **< 0.5**

Si malgré ces 3 niveaux un FP passe : `support@omnividens.fr` →
humain Argos analyse → fix dans le batch v2 suivant.

### « Je peux marquer un finding comme FP moi-même ? »

**Pas en libre-service aujourd'hui — roadmap Pro+ T3 2026.** Le
mécanisme `confidence_score` filtre auto les FP probables, mais le
bouton « Marquer FP » côté dashboard arrivera dans une release
ultérieure (cf. D-015).

En attendant : `support@omnividens.fr` avec le `scan_id` + le
`finding_id` + ton analyse pourquoi c'est un FP. Un humain regarde,
ajuste le module si la cause est généralisable, et te confirme dans
la semaine.

### « Pourquoi votre 0 FP n'est pas un 0 absolu ? »

Honnêtement : **« 0 FP » est un objectif d'industrialisation, pas une
garantie absolue.** Le marché DAST a longtemps vécu avec 30-50 % de FP
(scans qui crachent 200 findings dont 100 sont du bruit).

Argos vise **< 1 % de FP** dans des conditions normales (cible bien
configurée, auth recipe correcte, profil de scan adapté). Les 66 bugs
post-v2 documentés sont notre track record industriel, pas un argument
publicitaire.

Cas limite : un site qui répond 200 OK à n'importe quoi (catch-all
HTML) peut générer du bruit dans certains modules. C'est le cas
d'usage rare où le `confidence_score` peut filtrer trop strict ou pas
assez — d'où le filet de sécurité support humain.

---

## 9. Support, SLA, downgrade

### « C'est quoi votre support par tier ? »

| Tier | Canal | SLA |
|---|---|---|
| Free | KB + Discord public | best effort |
| Pro 39 € | Email | < 72 h |
| Team 129 € | Email | < 24 h |
| Pro Max 249 € | Slack dédié | < 8 h |

Pour du support enterprise 24/7 avec SLA contractuel : **Custom
contact ≥ 5 000 €/mois**.

### « Je peux downgrader Pro Max → Team / Team → Pro ? »

Oui. **Conservation 90 jours** des features du tier supérieur en
lecture seule, puis bascule réelle. **Watch désactivé immédiatement**
(pour les downgrades depuis Pro Max).

Pas de remboursement au prorata sauf droit conso EU 14 j (documenté
en CGV).

### « Je peux annuler à tout moment ? »

Oui :

- **Mensuel** — annulation effective à fin de la période en cours, tu
  gardes l'accès jusqu'à la fin du mois payé
- **Annuel** — fin de période = fin de l'année payée. Pas de
  remboursement au prorata sauf droit conso EU 14 j

Pas de prorata cash-back, c'est standard SaaS. Tu peux annuler depuis
ton compte ou écrire à `contact@omnividens.fr`.

→ Cf. [`pricing.md` § 7](pricing.md#7-refund--cancellation--downgrade).

### « Vous avez un Discord communautaire ? »

Oui — tous les users Free et Pro+ peuvent rejoindre le Discord public
Argos. **Salons** : `#general` (Q&R communautaires), `#bug-reports`
(remontée FP / bugs), `#feature-requests` (roadmap discussions),
`#release-notes` (changelog technique).

Lien d'invitation depuis le dashboard ou
[omnividens.fr/discord](https://omnividens.fr/discord).

Pour les Pro Max : Slack dédié privé en parallèle (pas Discord), avec
réponse SLA < 8 h ouvrées.

---

## 10. Questions diverses

### « Je peux recommander Argos à un ami / client et toucher une commission ? »

**Pas de programme de référencement formel au launch.** Si tu
recommandes Argos à un client de ton réseau et qu'il signe, écris à
`contact@omnividens.fr` — on peut discuter d'un mois offert ou d'un
accès Pro Max gratuit en remerciement, au cas par cas.

Programme structuré (commission % récurrente) en roadmap si la
demande organique est suffisante.

### « Vous avez une marque blanche ? »

**White-label PDF** disponible Pro Max (logo client → Team option,
white-label complet → Pro Max). White-label complet de la **plateforme
SaaS** (login, dashboard, domaine custom) = **Custom contact**, pas
self-serve.

### « Je suis pentester freelance, je peux vendre Argos en upsell à mes clients ? »

**Oui, on encourage.** Tu utilises Argos sur tes audits + tu
recommandes à ton client de garder Argos en monitoring continu après
ton audit. Pas de canal officiel partenaires au launch, mais un canal
direct via `contact@omnividens.fr` pour discuter du flow le plus
fluide (ex : compte client séparé, flux de paiement, etc.).

### « Vous formez à l'utilisation d'Argos ? »

**Pas de formation packagée au launch.** Pour Pro Max et Custom contact :
formation onboarding incluse (1-2 h Slack ou visio). Pour Free / Pro :
KB + Discord public + tutoriels courts dans la doc en ligne.

Si tu cherches **une formation pentest générale** (pas spécifique
Argos), on redirige vers **HackTheBox**, **OffSec OSCP**, ou des
formateurs FR comme **Le Comptoir Sécu**, **Sysdream**.

### « Je veux contribuer / proposer un module / signaler un bug. »

3 canaux selon le type :

- **Bug Argos** — Discord `#bug-reports` ou GitHub Issues du repo
  Omnividens-argos (privé pour l'instant, accès sur demande pour les
  Pro+)
- **Feature request module** — `contact@omnividens.fr` avec le besoin
  technique. Si on retient, ça part en roadmap.
- **Vulnérabilité Argos lui-même** — `security@omnividens.fr` (PGP
  fingerprint disponible dans la signature email). Pas de bug bounty
  formel mais reconnaissance publique + accès Pro Max gratuit pour
  les rapports valides

---

> **À noter** : cette FAQ couvre les ~50 Q&R les plus récurrentes au
> launch. Elle sera enrichie en P19 (maintenance) à partir des
> conversations réelles SupportBot. Le seuil pour ajouter
> une nouvelle Q&R est **« la même question est posée 3 fois par
> 3 users distincts »** — sinon ça reste dans les conversations
> support sans pollution KB.
