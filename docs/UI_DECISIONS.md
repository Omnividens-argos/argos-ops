# Argos Ops — UI Decisions (P16 Admin Control Panel)

> Cadre des choix design pour le Admin Control Panel (P16). Les choix
> structurants sont figés ici comme référence pour le code production
> Sprint 1+. Le mockup standalone (`mockup/admin-dashboard.html`) sert
> de **proof of concept visuel** — pas de prod.
>
> **À mettre à jour** avant le démarrage de la phase 16.A vraie
> (post-P7), avec une exploration `ui-ux-pro-max` complète comme
> recommandé dans
> [`ARGOS_OPS_PLAN.md` § 16.5](ARGOS_OPS_PLAN.md#165-design-philosophy).
>
> Dernière mise à jour : **2026-05-08** (mockup initial post-P4).

---

## 1. Inspirations cibles

| Source | Ce qu'on emprunte | Ce qu'on évite |
|---|---|---|
| **Linear** | Transitions ultra-rapides, raccourcis clavier (J/K nav, ⌘K palette), typographie Inter | Animations décoratives |
| **Grafana** | Dark-mode-first, densité info, statuts colorés, cards graphiques | Layout horizontal trop chargé |
| **Wazuh** | Sidebar fixe + status pills, modules en cards | Chrome lourd avec branding excessif |
| **Railway / Vercel** | Bonne combinaison « data + actions » sur la même vue | Look « SaaS marketing » pastel |

**Anti-patterns figés (à ne jamais faire)** :

- Pas de palette pastel Stripe / Notion (pas adapté à un cockpit opérateur)
- Pas de white space excessif — chaque pixel doit porter de l'info utile
- Pas d'animations décoratives — uniquement des transitions fonctionnelles
- Pas de dark/light toggle au launch — dark only (cohérent avec Wazuh /
  Grafana / Linear ; le panel ne sera ouvert qu'en début/fin de journée
  par le fondateur)

---

## 2. Palette canonique

### 2.1 Surfaces

| Token | Hex | Usage |
|---|---|---|
| `bg-base` | `#09090b` (zinc-950) | Fond principal de l'app |
| `bg-surface` | `#18181b` (zinc-900) | Cards, sidebar, topbar |
| `bg-surface-2` | `#27272a` (zinc-800) | Hover, active state, table header |
| `border` | `#3f3f46` (zinc-700) | Bordures cards, dividers |
| `border-subtle` | `#27272a` (zinc-800) | Dividers tableaux |

### 2.2 Texte

| Token | Hex | Usage |
|---|---|---|
| `text-primary` | `#f4f4f5` (zinc-100) | Titres, labels principaux |
| `text-secondary` | `#a1a1aa` (zinc-400) | Body, contenu secondaire |
| `text-tertiary` | `#71717a` (zinc-500) | Captions, métadonnées |
| `text-disabled` | `#52525b` (zinc-600) | Disabled states |

### 2.3 Accents (status colors)

| Token | Hex | Quand |
|---|---|---|
| `healthy` | `#10b981` (emerald-500) | Agent success, KPI vert, breaker reset |
| `info` | `#0ea5e9` (sky-500) | Liens, actions navigation, badge neutre |
| `warning` | `#f59e0b` (amber-500) | Escalades en attente humain, MRR baisse modérée |
| `danger` | `#f43f5e` (rose-500) | Breaker actif, agent failed, MRR chute > 5 % |

**Règle :** maximum 1-2 accents par vue à la fois. La vue par défaut
doit être à 95 % monochrome zinc, l'accent attire l'œil sur ce qui
demande attention.

---

## 3. Typographie

| Famille | Usage | Source |
|---|---|---|
| **Inter** (400, 500, 600, 700) | UI texte général | Google Fonts (CDN) |
| **JetBrains Mono** (400, 500) | Données, code, mono (timestamps, IDs, durées, output_summary) | Google Fonts |

**Tailles** (cohérence avec scale Tailwind par défaut) :

- `text-xs` (12px) — métadonnées, badges, labels uppercase
- `text-sm` (14px) — body principal, table cells
- `text-base` (16px) — paragraphes longs (rare dans le panel)
- `text-2xl` (24px) — KPIs principaux
- Bold weight `font-semibold` (600) pour les valeurs numériques importantes

**Letter-spacing** : `tracking-wider` (+0.05em) sur les uppercase
labels (`text-xs font-semibold uppercase tracking-wider text-zinc-500`)
— pattern Linear-like.

---

## 4. Densité et layout

### 4.1 Layout global

```
┌──────────┬───────────────────────────────────────────────────────┐
│ SIDEBAR  │  TOPBAR (h-12)                                        │
│ (w-60)   ├───────────────────────────────────────────────────────┤
│          │                                                       │
│  Logo    │  MAIN (overflow-y-auto)                               │
│  Nav     │                                                       │
│  ...     │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐                     │
│          │  │ KPI │ │ KPI │ │ KPI │ │ KPI │                     │
│  Status  │  └─────┘ └─────┘ └─────┘ └─────┘                     │
│          │                                                       │
│          │  ┌─────────────────────────────────┐ ┌──────────┐    │
│          │  │ Agents grid 4 cards             │ │ Breakers │    │
│          │  └─────────────────────────────────┘ │  + KPI   │    │
│          │                                       │ secondaire│    │
│          │  ┌─────────────────────────────────┐ │           │    │
│          │  │ Latest runs table               │ │           │    │
│          │  └─────────────────────────────────┘ └──────────┘    │
└──────────┴───────────────────────────────────────────────────────┘
```

### 4.2 Spacings canoniques

- Sidebar width : `w-60` (240px) — assez large pour labels Nav clairs
- Topbar height : `h-12` (48px) — minimal mais lisible
- Main padding : `p-6` (24px)
- Card padding : `p-4` (16px) sur cards info, `p-5` (20px) si table
- Gap entre cards : `gap-3` (12px) — densité Wazuh/Linear
- Border radius : `rounded-md` (6px) — pas trop arrondi (esprit cockpit)

### 4.3 Responsive

- **Desktop > 1280px** : layout 4 colonnes pour KPIs et agents
- **Desktop 1024-1280px** : layout 2 colonnes
- **Tablette < 1024px** : sidebar collapsable
- **Mobile < 768px** : sidebar en drawer overlay, **focus sur Overview
  + Agents Control uniquement** (cf. `ARGOS_OPS_PLAN.md` § 16.5 — usage
  mobile = pilotage rapide depuis le tel, pas KB editor)

---

## 5. Composants canoniques

### 5.1 Status pill

Petit badge coloré qui indique le statut (success / failed / inactive /
killed_by_breaker). Format :

```html
<span class="bg-healthy/15 text-healthy px-2 py-0.5 rounded text-[10px]
             font-medium uppercase tracking-wide">
  success
</span>
```

Backgrounds en `/15` (15 % opacity) pour rester sobres ; texte en
couleur pleine.

### 5.2 KPI card

Card pour les indicateurs Overview (MRR, Leads, etc.) :

```html
<div class="bg-zinc-900 border border-zinc-800 rounded-md p-4
            hover:border-zinc-700 transition-colors">
  <div class="text-[11px] text-zinc-500 uppercase tracking-wider">MRR</div>
  <div class="mt-1 flex items-baseline gap-2">
    <span class="text-2xl font-semibold mono">1 234 €</span>
    <span class="text-xs text-healthy">+5.2% vs S-1</span>
  </div>
  <div class="mt-1 text-[11px] text-zinc-500">Stripe live</div>
</div>
```

### 5.3 Agent card

Card opérationnelle qui combine **info + actions inline** (toggle ON/OFF,
Run now, Détails). Pattern Linear-like — toujours 1-2 actions
disponibles directement sans navigation.

---

## 6. Interactions & raccourcis clavier (Phase 16.B+)

À implémenter en phase 16.B / 16.C, **inspiré Linear** :

| Raccourci | Action |
|---|---|
| `⌘K` (Ctrl+K) | Command palette (recherche + actions globales) |
| `J` / `K` | Naviguer haut/bas dans une liste |
| `Enter` | Ouvrir détails de l'item sélectionné |
| `T` | Toggle ON/OFF de l'agent en focus |
| `R` | Run now de l'agent en focus |
| `Esc` | Fermer drawer / palette |
| `?` | Aide raccourcis (toujours dispo) |

Documentation à figer dans le panel sous le menu d'aide.

---

## 7. Stack technique (figée par § 16.3 du plan)

- **Backend** : FastAPI dans `argos_ops/ops_dashboard/app.py`
- **Frontend** : React + Vite + Tailwind 4 — cohérent avec le frontend
  SecHunter (réutiliser des composants si possible)
- **Real-time** : SSE (Server-Sent Events) — plus simple que WebSocket,
  suffit pour push état agents + breakers
- **Charts** : `recharts` (léger) ou `apexcharts` selon les besoins —
  à trancher en phase 16.A
- **Code editor (KB)** : Monaco (VS Code engine) — phase 16.D pour
  l'éditeur des fichiers KB
- **Auth** : Basic Auth via Caddy + IP allowlist + JWT 8h + TOTP
  optionnel (phase 16.D)

---

## 8. Phasage P16

Cf. `ARGOS_OPS_PLAN.md` § 16.6 :

| Phase | Sprint | Pages |
|---|---|---|
| **16.A — MVP** | Sprint 1 (post P7) | Overview + Agents Control read-only + Logs |
| **16.B — Control** | Sprint 2 (post P11) | + Toggle ON/OFF + Sliders + Run now + Breakers control |
| **16.C — Escalations** | Sprint 3 (post P14) | + Escalations queue + Settings |
| **16.D — Advanced** | Sprint 4 | + KB editor + KPIs avancés + 2FA TOTP |

**Aujourd'hui** : mockup standalone HTML pour valider la direction
visuelle. Le code production de 16.A démarre Sprint 1 post-P7.

---

## 9. Notes de mise à jour

### 2026-05-08 — mockup initial

- Fichier : [`mockup/admin-dashboard.html`](../mockup/admin-dashboard.html)
- Stack mockup : Tailwind CSS via CDN + Alpine.js + Inter/JetBrains Mono via Google Fonts. **Aucune dépendance npm**, ouvre directement dans un navigateur
- Données : DigestBuilder run réel (id=2 success, 5.11 s) ; les autres agents (EmailBot, SupportBot, FinanceBot) en `inactive`. _(Le mockup initial 2026-05-08 listait un « ChatBot widget » placeholder — retiré par [D-019](DECISIONS.md#d-019--abandon-d%C3%A9finitif-du-chatbot-widget-site-p8-cancelled).)_
- Validation visuelle direction : palette zinc + accent healthy/danger, layout sidebar+topbar+main, cards denses
- **Action de suivi avant code prod 16.A** : invoquer `ui-ux-pro-max`
  pour exploration plus large + valider les choix actuels (densité,
  raccourcis, mobile)
