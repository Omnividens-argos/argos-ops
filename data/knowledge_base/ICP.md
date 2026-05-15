# ICP — Ideal Customer Profile (Argos / Omnividens)

> Qui Argos cherche à servir, qui Argos ignore, comment chaque agent
> (OutboundBot, AdBot, SupportBot, FinanceBot) doit prioriser
> son effort.
>
> Source : interview fondateur en P3-M2 (2026-05-07). Référencé par tous
> les agents de qualification, scoring BANT, ad targeting et email triage.

---

## 0. TL;DR — qui on vise, qui on ignore

- **On vise** : scaleups SaaS B2B FR de **30 à 300 personnes**, stack moderne
  (cloud public + GitHub + CI/CD + ≥ 3 devs internes), portées par un **CTO**
  (`Marc` → **Team 129 €/mois**) ou un **Head of Security** (`Sarah` →
  **Pro Max 249 €/mois**), tous deux solvables en self-serve carte bleue.
- **On ne vise pas** : TPE < 10 personnes (LTV < CAC), grands comptes >5000
  (procurement 9-12 mois sans SOC2 chez nous), consultants en marque blanche
  (cannibalisme), startups pre-seed sans surface d'attaque réelle.
- **Marché de départ** : France + Belgique francophone + Suisse romande +
  Luxembourg, **FR uniquement** côté KB / landing / chat (EN dans 6-12 mois).

---

## 1. Personas prioritaires

### Persona n°1 — Marc Lefèvre, CTO de scaleup SaaS B2B FR (cœur de cible)

| Attribut | Valeur |
|---|---|
| Titre | CTO / Head of Engineering / VP Engineering |
| Taille boîte | 30-150 personnes, série A ou bootstrap rentable |
| Stack | Next.js / FastAPI / Postgres / AWS ou GCP / GitHub / GitHub Actions |
| Équipe sécu | Aucune dédiée — Marc porte la sécu en plus du reste |
| Dépense sécu actuelle | €8k-25k/an : Acunetix Online OU Detectify OU Intruder + 1 pentest annuel manuel |
| Frustration n°1 | Le pentester externe couvre 30 % du périmètre pour 15k€/an |
| Achat | **Self-serve carte bleue** sur **Team 129 €/mois** (cœur de cible) ou **Pro Max 249 €/mois** si gros périmètre. Signe en 5 min sans demander à personne |

**Test mental quand on code Argos :** « Est-ce que Marc, en 10 minutes, peut
comprendre ce que fait Argos et lancer un scan utile sans que je doive
l'onboarder ? » Si non, c'est mort.

**Cible prioritaire pour :** AdBot (LinkedIn ciblé CTO scaleup FR + Google
Search « scanner DAST sans faux positif »), OutboundBot (cold email LinkedIn
à froid), SupportBot (la majorité des emails entrants
`contact@omnividens.fr`).

---

### Persona n°2 — Sarah Khelifi, Head of Security en fintech / healthtech (deuxième cercle)

| Attribut | Valeur |
|---|---|
| Titre | Head of Security / RSSI / CISO / DevSecOps Lead |
| Taille boîte | 100-300 personnes |
| Pression | Compliance PCI / SOC2 / HDS / DORA en cours |
| Stack actuelle | Acunetix ou Detectify qui crache 200 FP par scan, équipe ignore les rapports |
| Besoin | Outil qui rentre dans le pipeline CI + rapports lisibles par auditeur externe |
| Dépense sécu actuelle | €40k-120k/an : Acunetix Premium + Snyk + pentest semestriel + outil compliance (Vanta/Drata) |
| Achat | **Pro Max 249 €/mois** en self-serve (ou annuel 199 €/mois). Si SLA contractuel / MSA / data residency stricte requis → bascule **Custom contact ≥ 5 000 €/mois**. Cycle 2-3× plus long que Marc |

**Argument décisif pour Sarah** : BYOK + 0 € SaaS récurrent IA. Elle ne peut
pas envoyer ses scan results vers une API US d'OpenAI sans accord interne. Le
BYOK lui donne le contrôle total — c'est le **clincher au moment de signer**,
pas le headline.

**Cible prioritaire pour :** OutboundBot (signal LinkedIn « embauche
Compliance Officer » ou « certif SOC2 démarrée »), demande de démo via le
site (qualif inbound).

---

### Persona n°3 — Thomas, freelance pentester / bug bounty hunter (audience evangelist)

| Attribut | Valeur |
|---|---|
| Profil | Solo, paie de sa poche, achète en 5 min carte bleue |
| Ticket | Bas (€19-30/mois, plan Free → Pro) |
| Rétention | **Faible** — prend 1 mois pour un programme bug bounty, puis stop |
| Valeur réelle | **Évangélisation** : c'est lui qui va poster sur Mastodon / Hacker News « Argos a trouvé un truc que Burp avait raté » |
| Ratio évangélisation/€ | Excellent — soutient la légitimité technique côté prospect Marc |

**🚧 Garde-fous commerciaux (à respecter par tous les agents) :**

- ❌ **Zéro effort OutboundBot** — pas de cold email à froid sur cette audience
- ❌ **Zéro budget AdBot Google Ads ou LinkedIn Ads** — coût d'acquisition >
  ticket annuel
- ✅ **Présence organique uniquement** : Mastodon `infosec.exchange`,
  Hacker News, blog technique en EN à partir de l'horizon EN (6-12 mois)
  (Reddit retiré du périmètre Argos Ops — [D-022](../../docs/DECISIONS.md#d-022--retrait-d%C3%A9finitif-de-reddit-du-p%C3%A9rim%C3%A8tre-argos-ops))
- ✅ ContentBot peut produire du contenu visant cette audience à condition
  zéro dépense pub

**Pourquoi on le garde dans l'ICP** : il est rentable en zéro-CAC, et sa
viralité technique alimente le funnel B2B (Marc trouve Argos via le tweet
de Thomas).

---

## 2. Taille d'entreprise — table décision

| Taille | Effectif | Décision | Pourquoi |
|---|---|---|---|
| TPE | < 10 | ❌ **non merci** | Ticket < €50/mois, pas de besoin sécu réel, 3 h pour expliquer un CVSS, churn au mois 2. CAC > LTV. |
| **PME** | **10-250** | ✅ **oui — cœur de cible** | Assez tech pour comprendre les findings, surface d'attaque qui justifie un scan continu, achat self-serve ou démo simple. CTO/Head Eng signe sans procurement. **80 % de la roadmap commerciale doit pointer ici.** |
| ETI | 250-5000 | 🟡 **peut-être, opportuniste** | Bon ticket (€20-80k/an) mais procurement 3-6 mois, ISO 27001 questionnaire, audit DPO. **Inbound : on prend. Outbound : trop coûteux pour solo.** |
| Grands comptes | > 5000 | ❌ **pas maintenant** | Procurement 9-12 mois, RFP 200 questions, exigence SOC2 chez l'éditeur (qu'on n'a pas), penalty clauses. **Recalage honnête** : « pas pour vous aujourd'hui, revenez dans 18 mois ». |

**Sweet spot non négociable : 30-300 personnes.** Au-dessus, le coût-temps
explose. En-dessous, le ticket meurt.

---

## 3. Géographie & langue

### Marché de départ (Sprint 1-3)

**FR + Belgique francophone + Suisse romande + Luxembourg.**

Raisons :
- Capacité à supporter en solo : un dev FR de San Francisco qui ping à 22 h,
  ça flingue la qualité du support
- Accessibilité ICP : les CTO de scaleup FR sont joignables (LinkedIn DM,
  FIC, NDH, BSides Paris, salons Cyber). Un VP Eng américain reçoit 200 cold
  mails/semaine, on n'existe pas
- Procurement : la France/Belgique acceptent encore qu'un éditeur n'ait pas
  SOC2. Aux US, sans SOC2, on n'existe pas au-dessus de 50 personnes

### Roadmap géographique

| Horizon | Marché | Déclencheur |
|---|---|---|
| Sprint 1-3 | FR + BE + CH + LU | — (par défaut) |
| Sprint 4 + 6-12 mois | DACH (DE / AT / CH allemande) | Marché énorme + culture compliance qui valorise le BYOK |
| 12-18 mois | NL / ES | KB EN stable + 1 employé support EN |
| 18+ mois | Monde anglophone via product-led growth | Hacker News, Mastodon `infosec.exchange`, blog technique EN |

### Langue de la KB / landing / emails

- **Landing `omnividens.fr` : FR uniquement** au démarrage
- **KB SupportBot : FR uniquement** (les chunks KB sont en français)
- **Emails entrants `contact@omnividens.fr` : FR uniquement** au démarrage.
  Si un visiteur écrit en EN, SupportBot répond en FR avec excuse + invite
  à reformuler en FR (KB EN reportée au 12-18 mois — cf. tableau).
- Blog : FR principal, articles EN ponctuels visant Persona 3 (Hacker News /
  Mastodon infosec) à partir du Sprint 2

---

## 4. Déclencheurs d'achat (3 derniers mois) — fuel pour OutboundBot

Liste prioritisée par **actionnabilité** (capacité d'OutboundBot / AdBot à
détecter le signal et timer l'approche) :

| # | Déclencheur | Signal détectable | Timing | Score actionnabilité |
|---|---|---|---|---|
| 1 | **Renouvellement Acunetix / Detectify imminent** | Date signature initiale (case studies du concurrent sur LinkedIn) → +60 j avant anniversaire | 60 j avant | ⭐⭐⭐⭐⭐ |
| 2 | **Démarrage certif SOC2 / ISO 27001 / HDS / PCI** | Embauche Compliance Officer / Head of Security < 90 j (LinkedIn) | post-embauche | ⭐⭐⭐⭐⭐ |
| 3 | **Bug bounty program qui démarre** | Nouveau programme HackerOne / YesWeHack < 60 j | post-création | ⭐⭐⭐⭐ |
| 4 | **Faille publique chez un concurrent / dans la stack** | CVE high-profile (Log4Shell, MoveIt, Okta, …) | 1-7 j post-publication | ⭐⭐⭐⭐ |
| 5 | **Pentest annuel moisi** | Difficile à détecter externe — signal faible. Plutôt à capter via un mail entrant `contact@omnividens.fr` qui mentionne un pentest récent | Q4 (cycle budgétaire) + Q1 (post-rapport) | ⭐⭐ |
| 6 | **Nouveau Head of Security / RSSI** | Poste créé < 90 j (LinkedIn) — recoupe avec #2 | post-arrivée | ⭐⭐⭐⭐ |
| 7 | **Dev sénior frustré par un scan FP** | Signal organique : tweets, posts Hacker News / Mastodon mentionnant Snyk/Acunetix avec frustration | continu | ⭐⭐⭐ (organique, pas outbound) |

**Priorité OutboundBot :** déclencheurs 1, 2, 3, 6 (signaux LinkedIn fiables).
**Priorité AdBot :** retargeter sur déclencheur 4 (audience qui a recherché
le CVE high-profile dans les 7 jours).

---

## 5. Anti-ICP — qui on recale, comment

### Anti-ICP n°1 — Le consultant / pentester en marque blanche

**Pourquoi non :** Argos n'est pas un toolkit de revente, on vend en direct.
S'il facture 500€/jour de pentest manuel à son client en utilisant Argos sous
le capot, on prend tout le risque sans la marge. Et il devient concurrent
frontal de nos vrais clients qui pourraient aller le voir à la place.

**Recalage gentil (script verbatim) :**

> « Argos est destiné à un usage en direct par les équipes internes du client
> final. Si tu veux un outil de pentest pro à intégrer dans ta prestation,
> regarde plutôt Burp Suite Pro Enterprise ou Pentest-Tools. Si ton client a
> les moyens, fais-lui essayer Argos en parallèle de ta mission, ça lui
> donnera de la visibilité continue entre deux audits. »

### Anti-ICP n°2 — La startup pre-seed (3-8 personnes)

**Pourquoi non :** aucune surface d'attaque réelle, le produit n'est même pas
en prod, le CTO va churner après 1 scan, ça pollue les métriques. Ticket
≤ €19/mois, en dessous du coût de support.

**Recalage gentil (script verbatim) :**

> « Honnêtement à votre stade, vous avez plus à gagner en activant le 2FA
> partout et en lisant les guides de durcissement de votre cloud. Revenez
> nous voir quand vous aurez votre premier client B2B qui exige une certif
> ou un scan de sécurité — là on sera utiles. »

### Anti-ICP n°3 — Le directeur achats grand compte avec un RFP de 80 pages

**Pourquoi non :** pas de SOC2, pas de DPO interne, pas d'équipe légale qui
négocie un MSA. Cycle de signature 9 mois pour un revenu pas garanti.

**Recalage gentil (script verbatim) :**

> « Notre format actuel ne correspond pas à votre cadre achat. Pour un
> déploiement de cette ampleur avec exigences SOC2 / ISO certifiées chez
> l'éditeur, je vous recommande Pentera, Cobalt ou Detectify Enterprise — ils
> ont la structure pour répondre à un RFP de cette envergure. Argos vise les
> équipes qui peuvent acheter via abonnement direct CTO. »

### Anti-ICP n°4 — Le mec louche qui veut « tester un site qui m'a arnaqué »

**Pourquoi non :** illégal, ruine notre réputation si on laisse passer.

**Recalage :** signup bloqué + redirection vers la page « Usage légal » +
email manuel si insistance, lien vers les CERT. **Aucune négociation.**

---

## 6. Stack tech & maturité — les 8 cases du scoring lead

OutboundBot, SupportBot et le formulaire signup utilisent ce scoring pour
qualifier en `bant_score` (cf. CRM `leads.bant_score`).

| # | Case | Idéal (= +1) | Disqualifiant (= -2) |
|---|---|---|---|
| 1 | **Hébergement** | Cloud public AWS / GCP / Azure (≥ 80 % du périmètre) | 100 % on-prem fermé sans accès Internet |
| 2 | **Repo** | GitHub / GitLab (cloud ou self-hosted) avec ≥ 1 repo applicatif | Aucun repo / code vendor-locked |
| 3 | **CI/CD** | GitHub Actions / GitLab CI / CircleCI capable d'intégrer un job SARIF | « On déploie en SSH manuellement » |
| 4 | **Devs internes** | ≥ 3 devs internes capables de lire un finding et patcher | 0 dev interne (tout sous-traité offshore) |
| 5 | **Maturité sécu** | A déjà fait ≥ 1 pentest, ou a un programme bug bounty, ou connaît OWASP | « C'est quoi un CVE ? » |
| 6 | **Stack appli** | Web (REST / GraphQL / SPA) + mobile + ≥ 1 service cloud (S3, Lambda, K8s) | Pure WordPress sans API ni dev |
| 7 | **Surface en prod** | ≥ 1 domaine public accessible avec auth + ≥ 1 endpoint API | App interne uniquement, accessible que via VPN |
| 8 | **Maturité d'achat** | A déjà signé un SaaS B2B sans 6 mois de procurement (Linear, Notion, Vercel, Stripe…) | Tout passe par bon de commande papier validé par 4 niveaux |

**Règles de scoring :**

- **6/8 cases idéal cochées** → lead **chaud**, OutboundBot envoie un cold
  mail personnalisé sous 24 h
- **4-5/8 cases** → lead **tiède**, mis en file pour relance ContentBot
  (newsletter / blog)
- **< 4/8 cases** → poliment recalé via script Anti-ICP correspondant
- **≥ 1 disqualifiant détecté** → bascule directement en recalage, peu
  importe le reste du score

---

## 7. Budget & motion d'achat

### Comment l'ICP idéal achète

| Tier | Range | Motion | Persona type |
|---|---|---|---|
| Free | 0 € | **Self-serve, sans carte bleue** | Thomas occasionnel, Marc qui goûte |
| Pro | 39 €/mois | **Self-serve carte bleue** (signup site, < 5 min) | Thomas régulier, side-project Marc |
| **Team** | **129 €/mois** | **Self-serve carte bleue** | **Marc CTO scaleup — cœur de cible** |
| **Pro Max** | **249 €/mois** | **Self-serve carte bleue** (ou démo + contrat annuel) | **Sarah Head of Sec mid-market** |
| Custom contact | ≥ 5 000 €/mois sur devis | Demo + MSA + cycle 2-3× plus long | Sarah avec SLA contractuel / data residency stricte |
| (futur, > 18 mois) | €30k+/an | Procurement complexe (à éviter tant qu'on n'a pas la structure) | — |

### Dépense actuelle estimée par persona

| Persona | Outils typiques | Budget annuel |
|---|---|---|
| Marc (scaleup CTO) | Acunetix Online OU Detectify OU Intruder + 1 pentest annuel | €8k-25k |
| Sarah (Head Sec fintech) | Acunetix Premium + Snyk + pentest semestriel + outil compliance (Vanta/Drata) | €40k-120k |
| Thomas (freelance) | Burp Pro €475/an + Nuclei gratuit + Caido | €500-1500 |

> **Note pricing :** phrase clinchante canonique = **« 0 faux positif, 130
> modules entre 39 € et 249 €. Acunetix démarre à 350 € pour 1 site. »** La
> grille tient le **20-40 % moins cher** sur tout le segment SaaS comparable
> (Intruder, Probely, Acunetix). Détail concurrence + sources dans
> [`pricing.md`](pricing.md). Ici
> on retient juste la fourchette pour le scoring.

### Argument BYOK / 0 € SaaS récurrent IA — résonance par persona

| Persona | Force de l'argument | Position dans le pitch |
|---|---|---|
| **Sarah** (fintech / healthtech / défense / public) | 🔥 **Très fort** — clincher au moment de signer | Pas le headline, mais le clincher en deuxième ligne |
| Marc (scaleup généraliste) | 🟡 **Moyen** — il s'en fout un peu, son code n'est pas sensible. Retient « ah cool, l'IA me coûte rien » | Bonus, pas headline |
| Thomas (freelance) | 🔥 **Fort** — il a déjà sa clé Anthropic, il économise vraiment | Argument secondaire |

**Règle absolue : le headline c'est « 0 faux positif ». BYOK c'est la cerise.**

---

## 8. Signaux d'achat — triage en 5 secondes

Quand un signup, mail entrant, ou vue LinkedIn arrive, SupportBot / OutboundBot
/ AdBot scannent ces signaux dans cet ordre.

### Signaux verts (= « va convertir »)

| Signal | Détail |
|---|---|
| **Titre dans la signature** | CTO, Head of Security, Head of Engineering, VP Engineering, DevSecOps Lead, RSSI, CISO, Lead SRE, Founding Engineer |
| **Email de domaine pro custom** | `@boite.fr`, `@boite.io`, `@boite.com` — pas gmail / proton / outlook |
| **Mail formulé en français technique précis** | « On a 3 services web sur AWS derrière Cloudflare, on cherche à automatiser les scans entre nos pentests annuels » |
| **Cible mentionnée explicitement** | Un domaine concret, une stack précise (« Next.js + FastAPI + RDS »), un cas d'usage (« on prépare SOC2 pour Q3 ») |
| **Mots-clés spécifiques** | `faux positif`, `pipeline CI`, `SARIF`, `CVSS`, `OWASP`, `shift left`, `continu`, `SOC2`, `PCI`, `DORA` |
| **Boîte de 30-300 personnes** | Vérification rapide LinkedIn |
| **Profil LinkedIn avec passé technique** | Engineer → Senior → Lead → CTO. **Pas** Sales → Marketing → Head of Security |
| **Demande précise avec cas concret** | Parfois un screenshot du dashboard d'un autre outil avec « regardez ce truc, vous le détectez ? » |

### Signaux rouges (= « va perdre du temps »)

| Signal | Détail |
|---|---|
| **Demande générique** | « Bonjour, j'aimerais en savoir plus sur votre offre » → générique, probablement étudiant ou veille concurrentielle |
| **Mail @gmail.com + titre Founder** | Boîte créée il y a 2 mois |
| **Demande de comparatif exhaustif** | « Pouvez-vous nous envoyer un comparatif vs [tous nos concurrents] ? » → procurement déguisé qui ne signera jamais |
| **Mention de budget ridicule** | « On a un budget de 50€ pour la sécurité » → recale immédiatement |
| **Aucun titre dans la signature** | Juste un prénom → 9 fois sur 10 c'est un bot scrapeur ou un broker de leads |

### Règle de pondération

> Le bon prospect te ping en parlant **déjà de sa stack**. Le mauvais te ping
> en demandant **un PDF**.

---

## 9. Décisions différées (à ne pas re-débattre)

| Sujet | Décision actuelle | Trigger de revue | Date estimée |
|---|---|---|---|
| **Programme « Argos for Pentesters » (marque blanche)** | ❌ Anti-ICP. Pas de licence de revente | **Double trigger :** (a) MRR Argos > €10k/mois ET (b) P19 atteint (système Argos Ops mature) | 2026 Q4 → 2027 |
| **Landing / KB en EN** | FR uniquement | Embauche d'un employé support EN OU MRR > €30k/mois | 2026 H2 |
| **Marché DACH** | Pas avant Sprint 4 | KB FR mature + 1 employé bilingue FR/DE | 2027 |
| **Marché US / monde anglo** | Pas avant 18 mois | SOC2 entamé + KB EN + product-led growth validé | 2027 H2 → 2028 |
| **Acceptation de RFP grand compte** | Refus systématique | SOC2 obtenu + équipe légale + ≥ 5 employés | indéterminé |

**Règle :** si un sujet de cette table revient dans une discussion business,
**rappeler la décision et le trigger** — ne pas re-débattre tant que le
trigger n'est pas atteint.
