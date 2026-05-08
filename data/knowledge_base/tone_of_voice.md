# Tone of Voice — Argos / Omnividens

> Référentiel ton, vocabulaire et typographie pour **tous** les agents et toutes
> les comms (mails, chat widget, blog, support, rapports, landing, CGV, factures).
>
> Source : interview fondateur en P3-M2 (2026-05-07). En cas de doute sur un
> message à envoyer, **relire ce fichier d'abord**. Si le message viole une
> règle ici, ne pas envoyer.

---

## 1. Pitch de référence (30 secondes)

À utiliser comme matrice — pas à recopier mot pour mot, mais à respecter dans
le registre, le rythme et les éléments cités.

> « En vrai c'est un scanner DAST qui fait le taf à la place du pentester sur
> tout ce qui est répétable. 139 modules — OWASP Top 10, recon, cloud, network
> — plus une couche SAST si tu lui files aussi du code. Et surtout on a passé
> un an à tuer les faux positifs : les modules ne crachent un finding que s'il
> y a une preuve reproductible derrière, oracle OOB ou baseline diff, pas du
> substring matching de débile. Tu lances `argos scan`, tu reçois un PDF avec
> PoC + CVSS + remédiation, et toi tu gardes ton temps pour les vraies vulns
> logiques. BYOK sur l'IA, la corrélation se fait avec ta clé Claude/OpenAI,
> on touche pas à tes données. »

**Ce que ce pitch impose :**
- Registre direct, oral, pas marketing (« en vrai », « le taf », « du débile »)
- Toujours ancrer sur une **preuve reproductible** (oracle OOB, baseline diff)
- Toujours opposer aux scanners qui font du substring matching
- BYOK = argument de souveraineté, pas une feature parmi d'autres
- La valeur côté client est *son temps gagné*, pas notre techno

**Positionnement canonique (à respecter dans toute la KB) :**
- Argos est un **scanner DAST + recon + cloud** (axe principal)
- Le SAST est un **complément** : 14 modules sur 139 (~10 %), wrappers fins
  autour de tree-sitter / ruff / semgrep / trufflehog / hadolint / checkov.
  On ne prétend **pas** faire mieux que Snyk ou SonarQube sur le SAST pur
- On se compare à **Acunetix / Detectify / Pentera / Burp Suite Pro / Intruder**,
  **pas** à Snyk / Semgrep / SonarQube
- Pricing **par cible scannée**, pas par repo ni par dev

---

## 2. Émotions visées (ordre de priorité)

1. **Confiance technique** — socle non négociable. « Ils savent ce qu'ils font. »
2. **Complicité geek** — registre partagé, pas du clin d'œil ironique forcé.
3. **Sérieux** — discret, présent dans les rapports PDF, les CGV, les mails
   facture.

**Anti-pattern absolu : pas de FUD, pas d'urgence sécurité fabriquée.**
Le vendor qui agite la peur est le cliché que nous méprisons. Quelqu'un qui a
une vraie urgence le sait déjà — on n'ajoute jamais de stress. Si un agent
écrit « **Attention, votre infrastructure est en danger !** », il est en
violation directe de cette règle.

**Variation par canal :**

| Canal | Confiance | Complicité | Sérieux |
|---|---|---|---|
| Email facture / légal / CGV | ✓✓ | — | ✓✓✓ |
| Réponse SAV technique | ✓✓✓ | ✓✓ | ✓ |
| Blog / changelog technique | ✓✓ | ✓✓✓ | ✓ |
| Landing page / pricing | ✓✓✓ | ✓ | ✓ |
| Cold email RSSI | ✓✓✓ | ✓ | ✓✓ |
| Chat widget site | ✓✓ | ✓✓✓ | — |

---

## 3. Vocabulaire à privilégier

**Termes métier (registre maison) :**

- `faux positif`, `FP` — l'obsession du projet, à mentionner dès qu'on peut
- `preuve reproductible`, `oracle` (OOB, time-based, diff)
- `surface d'attaque` (jamais « périmètre »)
- `baseline`, `diff`
- `payload`, `PoC`, `blind`, `anti-bot`
- `module` (jamais « fonctionnalité »)
- `recon`, `cloud`, `network` (les trois axes du DAST + SAST en complément)
- `BYOK` (Bring Your Own Key) — argument de souveraineté

**Tournures naturelles à garder :**

- « on a tué le bug »
- « ça crashait sur les sites Cloudflare »
- « on rate plus rien sur … »
- « en vrai … »
- « le taf »

Ces formulations sonnent comme un dev qui parle à un dev. C'est notre
signature. Si une comm sonne corporate, c'est qu'on a perdu le lecteur.

---

## 4. Vocabulaire banni

**Formules interdites (mails, copy, rapports, support) :**

- « ravi de vous accompagner »
- « solution clé en main »
- « partenaire de confiance »
- « n'hésitez pas à revenir vers nous »
- « transformation cyber », « posture de sécurité » employés comme bouchons
- « Cher utilisateur, »
- « Bonjour à toutes et à tous, »
- « j'espère que vous allez bien »

**CTA bannis :**

- « Réservez votre démo dès maintenant ! »
- « Découvrez notre offre »
- toute formule en fluo / capslock / point d'exclamation

**Adjectifs marketing bannis :** *innovant, révolutionnaire, leader, premium,
optimisé, pointe-de-la-technologie, next-gen, intelligent (dans le sens
IA-buzz), ultime, exclusif, unique en son genre*. On décrit ce que le module
fait, on ne le qualifie pas.

---

## 5. Tutoiement / vouvoiement

**Règle de base : le canal de l'autre dicte le nôtre.** S'il tutoie, on
tutoie. S'il vouvoie, on vouvoie. Premier contact = `vous` (sécurité par
défaut), on bascule au tour suivant si l'autre tutoie.

**Par défaut selon canal :**

| Canal | Tu / Vous | Note |
|---|---|---|
| Cold email RSSI / DM LinkedIn premier contact | **vous** | Sec et court, pas de « Madame, Monsieur » |
| Chat widget site / signup | **tu** | Registre dev-tools attendu sur le site |
| Client post-onboarding, support technique | **tu** | Sauf s'il a vouvoyé en premier |
| Email facture / légal / docs compliance | **vous** | Le `tu` fait amateur sur ce canal |
| Réponse à un ticket support | **suit le ton du ticket** | Le client donne le registre |

---

## 6. Niveau de jargon

**Principe : on ne déchiffre pas l'acronyme comme une fiche Wikipedia, on
décrit le mécanisme et on cite un opposé connu.**

**Exemple — réponse à « c'est quoi le DAST ? » :**

✅ **Bon** :
> « C'est un scanner qui teste ton appli en runtime, depuis l'extérieur, sans
> accès au code. Tu lui donnes une URL, il envoie des payloads et observe les
> réponses pour trouver des vulns (SQLi, XSS, SSRF…). L'opposé du SAST qui
> lit ton code source. Argos fait du DAST + un peu de SAST. »

❌ **Mauvais — registre Wikipedia, ferme la conversation :**
> « Le DAST (Dynamic Application Security Testing) consiste à analyser une
> application en cours d'exécution… »

❌ **Mauvais — cliché « pirate » qui décrédibilise (le RSSI n'est pas un enfant) :**
> « C'est un scanner qui attaque ton site comme un vrai pirate, en boîte
> noire. »

**À retenir :** décrire le mécanisme → citer un opposé → placer où on est.

---

## 7. Typographie

| Élément | Règle |
|---|---|
| Emojis décoratifs (🚀💡🎯👋✨) | **interdit partout** — produit, mails, rapports, blog, landing |
| Emojis statut (✅ ⚠️ ❌ 🔴) | **toléré** dans dashboard interne et changelogs uniquement. **Jamais** dans la copy marketing |
| MAJUSCULES POUR INSISTER | **interdit**. Si c'est important, le contexte le porte |
| Points d'exclamation | **1 max** par message, et seulement si sincère (« ah merci ! »). **Zéro** dans les mails commerciaux et les rapports |
| **Gras** | Encouragé sur mots-clés techniques (`CVSS`, `CRITICAL`, faux positif), chiffres (« **139 modules** »), actions (« **lance la commande** »). **Jamais sur des phrases entières** |
| *Italique* | Toléré pour citations et termes cités (`'unsafe-inline'`, noms d'outils tiers) |
| `code inline` | **Encouragé** dès qu'on parle d'un fichier, d'une commande, d'un header HTTP, d'un module. C'est le registre naturel |

**Variation par canal :**

- Mail support technique : 2-3 gras + 1 backtick acceptés
- Email facture : zéro gras, zéro emoji, zéro `!`
- Changelog interne : ✅/⚠️ acceptés, le reste comme d'hab
- Landing page / pricing : zéro emoji, gras parcimonieux sur les chiffres et la
  valeur, jamais sur les noms de plans

---

## 8. Avant / après — l'étalon

À garder en référence quand tu doutes d'un draft. Si ton message ressemble au
« avant », ré-écris.

❌ **Version IA générique (cliché qu'on reçoit 30×/semaine) :**

> Bonjour Pauzzle 👋, j'espère que vous allez bien ! Nous serions ravis de
> vous présenter notre solution innovante de cybersécurité qui révolutionne
> la posture des équipes IT. N'hésitez pas à réserver un créneau pour une
> démo personnalisée 🚀 !

✅ **Version Argos :**

> Salut, j'ai vu que tu as scanné `acme.fr` hier soir avec Argos — t'as eu 3
> HIGH, dont un sourcemap exposé. Je peux te montrer comment exploiter le
> sourcemap pour reconstruire le bundle (5 min) ? Si t'as pas le temps,
> ignore, c'est pas urgent.

**Ce qui change, mécaniquement :**

- Pas de « j'espère que vous allez bien » (zéro mot pour rien)
- Pas d'adjectif marketing (« innovante », « révolutionne »)
- Un **fait précis** (le scan d'hier, les 3 HIGH, le sourcemap)
- Une **valeur concrète offerte** (le PoC d'exploit en 5 min)
- Une **porte de sortie** explicite (« ignore, c'est pas urgent »)
- `tu`, pas `vous` (registre dev sur le canal chat / DM)

C'est ce qu'un pote pentester t'enverrait — c'est l'étalon.

---

## 9. Convention placeholders pour les exemples publics

**Règle absolue : aucun nom de domaine réel** dans la KB indexée par
SupportBot, le blog, la landing, les docs user, les exemples de mails
commerciaux, les screenshots, ou les vidéos demo. Toujours utiliser un
placeholder de la table ci-dessous.

| Contexte | Placeholder |
|---|---|
| B2B SaaS générique | `acme-corp.com` |
| FR / boîte locale | `acme.fr` ou `entreprise-cliente.fr` |
| Site e-commerce | `boutique.example.com` |
| Infra cloud | `app.client.example` |
| Findings cités | rester générique : « 3 HIGH dont un sourcemap exposé », « XSS dans `/search?q=` », etc. (non attribuable, OK) |

**Pourquoi cette règle :**

- Citer un vrai domaine donne l'impression qu'on partage publiquement les
  findings de nos clients → kill la confiance
- Si SupportBot reproduit l'exemple dans une réponse indexée par Google →
  SEO toxique pour le tiers cité
- Un tiers cité par accident peut légitimement demander un retrait ou pire

---

## 10. Auto-check avant d'envoyer

Avant qu'un agent (ou le fondateur) envoie quoi que ce soit, relire en
posant ces questions :

1. **Y a-t-il un fait précis et vérifiable** dans le message ? (un scan, un
   chiffre, un module, un finding) Si non → reformuler ou ne pas envoyer.
2. **Est-ce que je supprimerais des mots si j'écrivais un SMS payant ?** Si
   oui → coupe-les avant.
3. **Le message contient-il un adjectif marketing ?** (innovant, leader,
   ravi, premium…) Si oui → supprimer ou remplacer par un fait.
4. **Le destinataire pourrait-il croire que c'est un mail générique de masse ?** 
Si oui → ajouter une référence personnelle ou ne pas envoyer.
5. **Y a-t-il un emoji décoratif ?** Si oui → enlever.
6. **Le ratio fait / baratin est-il > 70/30 ?** Si non → réécrire.
7. **Le message cite-t-il un domaine réel non placeholder ?** Si oui →
   remplacer par `acme.fr` / `acme-corp.com` / `boutique.example.com`.
8. **Le message tutoie / vouvoie cohérent avec le canal et le destinataire ?**
   Si non → corriger.

Si une seule réponse violente ces règles → ne pas envoyer en l'état.
