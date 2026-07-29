# Design system

The rules the UI follows, and the reasoning behind the ones that look arbitrary.
Tokens live in `frontend/tailwind.config.js`; components in
`frontend/src/components/`.

## The one rule that explains most of the others

**Gold means the engine is making a claim.**

Accent colour is reserved for model output — podium probabilities, title odds,
the recommended strategy, the single primary action per view. It is never used
for navigation, borders, or decoration. A link is not a claim.

This is why `Button`'s `primary` variant is the only one that spends accent, and
why secondary links use `text-ink-dim`. A page with two primaries has no
primary.

## Colour

### Surfaces
`page` → `rail` → `surface` → `inset` → `inset2`, darkest to lightest. Cards sit
on `surface`; controls and ceremony blocks on `inset`; tooltips on `inset2`.

### Ink ramp
Lightest to darkest — the names are a ramp, not adjectives:

| Token | Hex | Contrast on card | Use |
|---|---|---|---|
| `ink` | `#eef1f5` | 17.15:1 | headings, primary values |
| `ink-soft` | `#dbe0e8` | 14.66:1 | body |
| `ink-muted` | `#aab3c0` | 9.18:1 | secondary body |
| `ink-dim` | `#8994a4` | 6.33:1 | labels, secondary links |
| `ink-faint` | `#7d8698` | 5.31:1 | small mono labels — **the floor** |
| `ink-fainter` | `#3f4756` | 2.08:1 | **decorative only** — never text |

Every step except `fainter` clears WCAG AA (4.5:1). `fainter` is for icons and
separators that sit beside a label; using it for text is a bug.

### Accent
Runtime-swappable (gold / cyan / violet) via the `--accent` CSS variable. Any
new accent must clear **3:1 at 0.9 alpha** on `surface-inset2`, because that's
what the focus ring uses — violet at 0.65 measured 2.69:1 and failed WCAG
1.4.11, which is why the ring is 0.9.

### Domain colours — never themed
Tyre compounds (`soft` red, `medium` yellow, `hard` white) and team colours are
**data**, not decoration. They do not follow the accent. A themeable compound
colour would be a lie about what the chart is showing.

### Charts
Recharts takes colour props, not classes, so charts need literals — but they get
them from `lib/chartTokens.ts`, not from thin air. Three near-duplicates had
drifted in before that existed (`#9a9aa6` vs `ink-dim`, `#1a212b` vs `line`,
`#ecedf0` vs `ink`). They all render as "grey" or "off-white", so nothing catches
them by eye.

## Typography

`Space Grotesk` (sans) · `IBM Plex Mono` (data, labels) · `Archivo Black`
(display). Mono is the app's voice for anything numeric or label-like.

Small steps, which a data app needs and Tailwind doesn't supply:

| Token | Size | Use |
|---|---|---|
| `text-micro` | 10px | dense table meta, chart ticks |
| `text-mini` | 11px | the workhorse mono label |
| `text-data` | 12px | numeric cells, chips |
| `text-data-lg` | 13px | emphasised data text |

Above 13px, use the standard Tailwind scale. **No arbitrary `text-[Npx]`** —
there were 124 of them across 8 values including half-pixels, which is a second
type scale nobody agreed to.

## Spacing

4px rhythm; 8px and 12px carry most of the layout. This is the cleanest system
in the app — keep it that way.

## Components

| Component | Variants | Notes |
|---|---|---|
| `Button` | `primary` `secondary` `ghost` `danger` × `sm` `md` | `loading` keeps focus (aria-disabled, not `disabled`); `pressed` sets `aria-pressed` |
| `Card` | default | `className` for padding/border overrides |
| `Metric` | `card` `cell` | `cell` for bordered grid layouts |
| `Badge` | tones | status and counts |
| `Segmented` | — | 2–4 mutually exclusive options. **Use this** instead of hand-rolling toggle rows |
| `Field` / `Select` / `Combobox` / `Slider` | — | form controls, all labelled |
| `DataTable` | `isHighlighted` | favourite-driver highlighting |
| `EmptyState` / `Skeleton` / `CardSkeleton` / `Spinner` / `ErrorNote` | — | every async surface needs all four states |
| `CommandPalette` / `ShortcutsHelp` | — | `role="dialog"`, focus-trapped, restores focus on close |

### When not to use `Button`
Colour swatches, driver-avatar tiles and nav rail items are `<button>` elements
for semantics but are bespoke by design — they're pickers whose whole content is
the affordance. Wrapping them in `Button` would fight it.

## Motion

Every decorative animation is gated on **both** `prefers-reduced-motion` and the
in-app Settings toggle (`[data-motion="off"]`). Both lists must be updated
together — `animate-f1pulse` was once in neither, which meant the Settings
toggle promised something it didn't deliver while ten elements kept pulsing.

Loading spinners are deliberately exempt: removing functional feedback costs
comprehension without protecting anyone.

## Accessibility floor

Non-negotiable, verified: skip link before the nav · visible focus ring, never
suppressed · all text ≥ 4.5:1 · every control has an accessible name · dialogs
carry role + label + focus trap · `lang` set · landmarks present.
