# Argos Ops — UI Decisions (Cockpit archi v2)

> **Source de vérité du design system** du cockpit Argos Ops (archi pôles v2,
> une seule app unifiée). Tout choix structurant (palette, typo, densité,
> z-index, états, composants, libs) est figé ici. Le code production des
> écrans (`argos_ops/ops_dashboard/frontend/`) doit s'y conformer.
>
> Refonte verrouillée le **2026-06-19** (session SF). Remplace le cadrage
> P16-mockup (2026-05-08) conservé en §11 Historique.
>
> Méthode : audit complet réel-vs-stub (Phase 0) + skill `ui-ux-pro-max`
> (règles a11y / interaction / z-index / charts / forms) + skill
> `frontend-design` (implémentation). Local-first **D-017** : toute lib est
> open-source npm, aucun service tiers payant.

---

## 0. Principe directeur

**Cockpit opérateur, pas SaaS marketing.** Dense, dark-mode-first (dual-theme),
chaque pixel porte de l'information utile. Inspirations conservées : **Linear**
(vitesse, ⌘K, raccourcis, Inter), **Grafana** (densité, statuts colorés),
**Wazuh** (sidebar fixe + status pills), **Vercel/Railway** (data + actions sur
la même vue). Anti-patterns : pas de pastel Stripe/Notion, pas de white-space
décoratif, pas d'animation gratuite, **pas de tout-mono** (cf. §3).

**Une seule app, un seul shell** (cf. §9) : Home global + 8 pôles + outils
globaux (Atelier, Console, Inbox, Outputs, Help, BotDetail). L'ancienne entrée
legacy `index.html`/`App.tsx` est retirée une fois les outils utiles migrés.

---

## 1. Palette (conservée — tokens `argos-*` dual-theme)

Tokens en CSS custom properties (`src/index.css`, triplets RGB) exposés par
Tailwind (`argos-*`, `<alpha-value>`). `darkMode: "class"`. Light **et** dark
passent WCAG AA 4.5:1. **Inchangé** — la base est saine.

### 1.1 Surfaces & texte

| Token | Dark | Light | Usage |
|---|---|---|---|
| `argos-bg` | `#09090b` | `#fafafa` | Fond app |
| `argos-surface` | `#18181b` | `#ffffff` | Cards, sidebar, topbar, drawer, modal |
| `argos-surface-2` | `#27272a` | `#f4f4f5` | Hover, header de table, zone enfoncée |
| `argos-border` | `#3f3f46` | `#d4d4d8` | Bordures cards/contrôles |
| `argos-border-subtle` | `#27272a` | `#e4e4e7` | Dividers de table |
| `argos-fg` | `#f4f4f5` | `#18181b` | Titres, valeurs |
| `argos-fg-secondary` | `#a1a1aa` | `#3f3f46` | Body |
| `argos-fg-tertiary` | `#71717a` | `#71717a` | Captions, eyebrows, métadonnées |
| `argos-fg-disabled` | `#52525b` | `#a1a1aa` | États désactivés |

### 1.2 Accents sémantiques

| Token | Dark | Light | Sens |
|---|---|---|---|
| `argos-healthy` | emerald-500 | emerald-600 | succès, vert KPI, breaker reset |
| `argos-info` | sky-500 | sky-600 | liens, neutre actif, focus ring |
| `argos-warning` | amber-500 | amber-600 | en attente, dégradé, dérive |
| `argos-danger` | rose-500 | rose-600 | breaker armé, échec, chute MRR |

**Règle figée : max 2 accents par vue.** Vue par défaut ≈ 95 % monochrome zinc ;
l'accent attire l'œil sur ce qui demande attention. Couleur jamais seule porteuse
de sens (toujours + icône/texte — `color-not-only`).

---

## 2. Échelle de couleur de données (charts)

Palette catégorielle accessible (au-delà des 4 accents sémantiques), pour séries
multiples — évite rouge/vert seuls (daltonisme). Ordre canonique :
`info (sky)` → `violet-500` → `emerald` → `amber` → `fuchsia-500` → `cyan-500`.
Gridlines `argos-border-subtle`. Contraste data ≥ 3:1, labels ≥ 4.5:1. Toujours
légende + tooltip + empty-state + skeleton (cf. §6 Chart, règles `chart`).

---

## 3. Typographie (CORRIGÉE — mono réservée aux données)

> **Décision clé de la refonte.** L'audit a montré que JetBrains Mono était la
> police *dominante* (labels, valeurs, prose). On corrige : **Inter = texte
> d'UI** (labels, body, titres, descriptions, boutons, nav), **JetBrains Mono =
> données uniquement** (nombres, montants, IDs, timestamps, durées, hash, code,
> `output_summary`, chemins). `number-tabular` : figures tabulaires mono sur les
> colonnes de table/prix/timers pour éviter le layout shift.

### 3.1 Familles

- **Inter** (400/500/600/700) — UI. `font-sans`.
- **JetBrains Mono** (400/500) — données/code. `font-mono`. `font-display: swap`.

### 3.2 Échelle de type figée (fini les `text-[9px]…[11.5px]` arbitraires)

| Token | px | Usage |
|---|---|---|
| `text-eyebrow` (=`text-[11px]`) | 11 | labels uppercase `tracking-wider` `argos-fg-tertiary` |
| `text-xs` | 12 | métadonnées, badges, cellules denses |
| `text-sm` | 14 | body principal, cellules de table, contrôles |
| `text-base` | 16 | paragraphes, inputs (≥16px = anti-zoom iOS) |
| `text-lg` | 18 | titres de section |
| `text-2xl` | 24 | valeurs KPI |
| `text-3xl` | 30 | KPI héro (Home) |

Poids : titres `font-semibold` (600), valeurs num `font-semibold`, labels `500`,
body `400`. Line-height body 1.5. Mesure de ligne 60-75 car. desktop. Wrapping
préféré à la troncature ; si troncature → ellipsis + tooltip.

---

## 4. Densité, espacement, layout

Rythme **4/8 px** strict (`spacing-scale`). Tiers verticaux : 8 / 12 / 16 / 24 / 32.

- Sidebar (rail) : `w-60` (240px) desktop ; **drawer overlay** < 1024px.
- Topbar : `h-12` (48px).
- Padding main : `p-6` (desktop), `p-4` (mobile).
- Card : `p-4` (info), `p-5` (table). Gap cards : `gap-3`.
- Radius : `rounded-md` (6px) contrôles/cards, `rounded-lg` modals/drawer,
  `rounded-sm` cellules viz, `rounded-full` toggle/dots.
- Container max desktop : `max-w-[1600px]` (cockpit large), grilles fluides.
- Touch target ≥ 44px (mobile), gap ≥ 8px entre cibles.

### 4.1 Layout shell

```
┌──────────┬─────────────────────────────────────────────────┐
│ RAIL     │  TOPBAR h-12 (breadcrumb · ⌘K · thème · santé)   │
│ w-60     ├─────────────────────────────────────────────────┤
│ Home     │  MAIN (overflow-y-auto, p-6)                     │
│ ─ Pôles  │   Tabs du pôle ───────────────────────           │
│ 8 items  │   ┌ KPI ┐┌ KPI ┐┌ KPI ┐┌ KPI ┐                   │
│ ─ Outils │   contenu onglet (table / kanban / charts…)      │
│ globaux  │                                                  │
│ Atelier… │   Drawer détail (slide depuis la droite) ▸       │
└──────────┴─────────────────────────────────────────────────┘
```

---

## 5. Z-index, focus, états (figés)

### 5.1 Échelle z-index (l'audit a trouvé z-40/z-50 mélangés → on fige)

| Couche | z | Éléments |
|---|---|---|
| base | `z-0` | contenu |
| sticky | `z-10` | headers de table sticky, topbar |
| dropdown | `z-20` | menus, combobox, popovers |
| drawer | `z-30` | drawer latéral + son scrim |
| modal | `z-40` | modal + son scrim |
| toast | `z-50` | toasts (n'attrape jamais le focus, `aria-live=polite`) |
| tooltip | `z-60` | tooltip/help |

Scrim modal/drawer : `bg-argos-bg/70 backdrop-blur-sm` (40-60 % d'isolation).

### 5.2 Focus ring (visible, clavier-first)

`focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-argos-info
focus-visible:ring-offset-2 focus-visible:ring-offset-argos-bg`. Jamais de
suppression du focus. Tab-order = ordre visuel. Skip-link vers `#main`.

### 5.3 États d'interaction (parité light/dark obligatoire)

| État | Convention |
|---|---|
| hover | `hover:bg-argos-surface-2` / `hover:border-argos-border` (transition 150ms) |
| focus | ring §5.2 |
| active/press | `active:scale-[0.98]` (`argos-press`, inhibé reduced-motion) |
| selected | fond accent `/15` + bord accent + (icône/poids) |
| disabled | `opacity-50 cursor-not-allowed` + `disabled`/`aria-disabled` |
| loading | skeleton si > 300ms ; bouton async → spinner + `disabled` |
| read-only | distinct du disabled (fond `surface-2`, pas d'interaction, lisible) |

---

## 6. Bibliothèque de composants (kit unifié unique)

Fusion des deux couches actuelles (`components/*` legacy + `poles/components/*`)
en **un seul kit** `src/components/ui/`. Tones unifiés sur l'enum sémantique
`neutral | healthy | info | warning | danger`. Conservés tels quels : Button,
Badge, Toggle, Slider, TextInput, Flash, StatusPill, Skeleton*, EmptyState,
MarkdownPreview, Tooltip, ThemeToggle.

### À CONSTRUIRE (aujourd'hui hand-rollés/dupliqués)

| Composant | Spec figée |
|---|---|
| **Tabs** | `role=tablist`, flèches ←/→, `aria-selected`, indicateur animé ; remplace les ~8 switch locaux. |
| **Modal** | 1 shell unique (scrim §5.1, Esc, click-outside, focus-trap, `aria-modal`) ; remplace les 3 copies. Confirme avant fermeture si dirty. |
| **Drawer** | panneau latéral droit (détail lead/fait/run/draft), slide-in depuis la source, scrim, Esc, focus-trap. |
| **DataTable** | tri (`aria-sort`), filtre, pagination/virtualisation (`react-window` ≥ 50 lignes), empty-state, skeleton, header sticky, figures tabulaires. |
| **FormField** | label visible + helper persistant + erreur sous le champ (`role=alert`), via **react-hook-form + zod** ; validation `onBlur` ; focus 1er champ invalide. |
| **Chart** | wrapper **Recharts** (Line/Bar/Area/Gauge), légende, tooltip clavier, empty/loading/error, `prefers-reduced-motion`, couleurs §2. Remplace les SVG maison `finance/charts.tsx`. |
| **KanbanBoard** | **dnd-kit** (accessible, alternative clavier au drag), colonnes = stades, drop → mutation, optimistic + rollback. |
| **Calendar** | grille mois/semaine, drag d'items (dnd-kit), preview slot ; éditorial (marketing) + RDV (vente). |
| **FileUpload** | `<input type=file>` + drag-drop + barre de progression + preview (CSV via **papaparse** avant POST ; docs Finance multipart). |
| **MarkdownEditor** | split édition/preview (réutilise MarkdownPreview), barre d'actions ; KB marketing, publications direction. |
| **SearchBox** | input debouncé + résultats ; full-text via **Fuse.js** (client) ou endpoint `/search` (serveur), recents/suggestions. |

---

## 7. Stack & librairies (figées — toutes open-source, D-017)

| Besoin | Lib | Pourquoi |
|---|---|---|
| Data-fetching | **@tanstack/react-query** | cache + stale-while-revalidate (fin du refetch au switch d'onglet), invalidation post-mutation, remplace `usePolling` artisanal |
| Charts | **recharts** | une seule lib viz (MRR/burn/runway/forecast/OKR/perf/projection) |
| Drag-drop | **@dnd-kit/core+sortable** | accessible (Kanban vente, calendrier, push veille) |
| CSV parsing | **papaparse** | preview client avant upload (leads vente) |
| Forms | **react-hook-form** + **zod** | validation alignée Pydantic |
| Recherche | **fuse.js** | full-text client (Mémoire/global) |
| Virtualisation | **react-window** | longues listes/tables (perf) |

Real-time : **WebSocket** (cohérent avec l'atelier/console existants) — canal de
changements `/api/ws/changes` (runs, inbox, breakers, handoffs, mémoire),
**fallback polling React Query** si déconnecté. Pas de SSE (on ne mélange pas).

Code-split par pôle (`React.lazy` + Suspense + skeleton). Bundle léger,
lazy-load des pages lourdes.

---

## 8. Motion (conservée, sobre)

Micro-interactions 150-300ms, transitions ≤ 400ms, jamais > 500ms. Keyframes
existantes : `argos-toast-enter`, `argos-fade-in`, `argos-skeleton`,
`argos-press`, `.theme-transition`. Easing `cubic-bezier(0.2,0.8,0.3,1)`. Exit
≈ 60-70 % de l'enter. **Tout inhibé sous `prefers-reduced-motion`.** Anime
transform/opacity uniquement (jamais width/height/top/left).

---

## 9. Unification (décision de la refonte)

- **Shell unique** = évolution de `PolesShell` (entrée `poles.html` conservée et
  renommée racine ; `index.html`/`App.tsx` legacy retirés après migration).
- **Navigation** = rail : **Home** (dashboard global) · séparateur · **8 pôles**
  (Veille, Marketing, Pub, Vente & RC, Finance & Conformité, Direction, Mémoire,
  SRE & Meta-Ops) · séparateur · **Outils globaux** (Atelier, Console, Inbox,
  Outputs, Help). `nav-state-active` visible, placement constant, ≥ 1024px
  sidebar / < 1024px drawer hamburger.
- **Outils globaux migrés** (aucun pôle ne les couvre) : Atelier (WS, RCE
  D-029/D-032 — verbatim), Console bot generate-then-act (WS LIVE/SHADOW),
  Inbox cross-pôle, Outputs (archive), Today→Home, Help (glossaire), BotDetail
  (seule surface de contrôle agent : run-now/toggle/pause/YAML).
- **Vues legacy supprimées** (dupliquées par un pôle) : Pipeline→Vente,
  CashCustomers→Finance/Vente, HealthCompliance→SRE/Finance, Runs→SRE,
  ServiceDetail, Agents (grille), Memory.tsx→Mémoire, bot/{MemoryTab,
  TravailTab,IODetailModal}. Endpoints backend uniques aux outils gardés
  (`/api/atelier/*`, `/api/agents/{n}/console/*`, `/api/inbox/*`,
  `/api/outputs/*`, `/api/agents/{n}/config|runs|perf`) **conservés**.

---

## 10. Accessibilité, responsive, perf (objectifs Phase 7)

- **WCAG 2.1 AA** : contraste ≥ 4.5:1 (clair ET sombre), ARIA labels sur
  inputs/boutons icône, focus ring §5.2, nav clavier complète, skip-link,
  `aria-sort` tables, `role=alert`/`aria-live` erreurs+toasts, `aria-modal`.
- **Responsive mobile-first** : rail→drawer, grilles 1/2/3 col, touch ≥ 44px,
  zéro scroll horizontal. Breakpoints **375 / 768 / 1024 / 1280 / 1440**.
- **Perf** : code-split par pôle, `react-window` (listes 50+), debounce
  recherche/filtre, cache React Query, `prefers-reduced-motion`, CLS < 0.1
  (réserver l'espace des charts/async).

---

## 11. Historique

### 2026-06-19 — Refonte cockpit archi v2 (session SF)
Ce document. Design system unifié, mono réservée aux données, kit composants +
libs figés, plan d'unification des 2 apps. Source : audit Phase 0 + skills
`ui-ux-pro-max` / `frontend-design`.

### 2026-05-12 — Dual-theme
Tokens `argos-*` light+dark via CSS vars, toggle Topbar, WCAG AA les deux.

### 2026-05-08 — Mockup initial P16
`mockup/admin-dashboard.html` (Tailwind CDN + Alpine), validation visuelle
direction (zinc + accents, sidebar+topbar+main dense). Proof of concept, pas prod.
