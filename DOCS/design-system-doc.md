# Design System Documentation
### From custom CSS to a Tailwind-based system

---

## 1. Purpose of this doc

This document translates the existing hand-rolled CSS design system (tokens, components, page patterns) into a design language that can be rebuilt on Tailwind CSS. It explains the visual system as it stands today, then shows how each piece maps onto Tailwind's config and utility classes, so the same look can be reproduced without maintaining a separate stylesheet.

The goal is not to change the aesthetic, it is to re-express it in a way Tailwind can generate directly.

---

## 2. Design philosophy

The system reads as a calm, editorial, "enterprise SaaS" look:

- A deep navy primary color carries brand weight, used sparingly as gradients on CTAs and hero surfaces.
- A neutral, layered surface hierarchy (six tonal steps from white to dim gray) creates depth without heavy borders or drop shadows.
- Warm amber is reserved as a tertiary accent, capped at roughly 5% of any screen, used for highlight moments only.
- Typography splits duties: Manrope (a geometric grotesque) for headlines and numbers, Inter for body and UI text.
- Shadows are soft and ambient rather than sharp, giving cards a "floating paper" feel instead of a hard drop-shadow look.
- Corners are consistently rounded, and radius increases with the size and importance of the container (small controls get 8 to 12px, hero panels and modals get 24 to 32px).

---

## 3. Color system

### 3.1 Semantic tokens (current CSS variables)

| Token | Hex | Role |
|---|---|---|
| `--surface` / `--surface-bright` | `#f8f9f9` | App background |
| `--surface-container-lowest` | `#ffffff` | Cards, panels, inputs |
| `--surface-container-low` | `#f3f4f4` | Sidebar, subtle fills |
| `--surface-container` | `#edeeee` | Hover states |
| `--surface-container-high` | `#e7e8e8` | Borders, dividers |
| `--surface-container-highest` | `#e1e3e3` | Strongest neutral fill |
| `--surface-dim` | `#d9dada` | Recessed areas |
| `--primary` | `#12283c` | Brand navy, primary actions |
| `--primary-container` | `#293e53` | Gradient end, secondary emphasis |
| `--on-primary` | `#ffffff` | Text/icons on primary |
| `--secondary` | `#506071` | Slate, secondary text and icons |
| `--secondary-container` | `#d3e4f8` | Secondary chip fills |
| `--tertiary-fixed` / `--tertiary-fixed-dim` | `#ffdcc5` / `#ffb783` | Amber accent (used sparingly) |
| `--on-surface` | `#191c1c` | Primary text |
| `--on-surface-variant` | `#43474c` | Secondary/body text |
| `--outline` / `--outline-variant` | `#74777d` / `#c4c6cd` | Borders, placeholder text |
| `--error` / `--error-container` | `#ba1a1a` / `#ffdad6` | Error states |
| `--success-color` | `#2d6a4f` | Success states |

There are also five "tone" variants used across metric and insight cards: navy, emerald, gold, slate, crimson. Each pairs a soft tint background with a matching icon/text color.

### 3.2 Mapping to Tailwind

Rather than keep raw hex values scattered through class names, extend Tailwind's theme with the same semantic names, so classes read `bg-surface`, `text-on-surface`, `bg-primary`, `text-on-primary`, etc. This keeps intent visible in markup instead of hex codes.

```js
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: '#f8f9f9',
          bright: '#f8f9f9',
          container: {
            lowest: '#ffffff',
            low: '#f3f4f4',
            DEFAULT: '#edeeee',
            high: '#e7e8e8',
            highest: '#e1e3e3',
          },
          dim: '#d9dada',
        },
        primary: {
          DEFAULT: '#12283c',
          container: '#293e53',
          fixed: '#cfe5ff',
          'fixed-dim': '#b3c9e2',
        },
        secondary: {
          DEFAULT: '#506071',
          container: '#d3e4f8',
        },
        tertiary: {
          fixed: '#ffdcc5',
          'fixed-dim': '#ffb783',
        },
        'on-primary': '#ffffff',
        'on-secondary': '#ffffff',
        'on-secondary-container': '#566677',
        'on-surface': '#191c1c',
        'on-surface-variant': '#43474c',
        'on-tertiary-fixed': '#301400',
        outline: {
          DEFAULT: '#74777d',
          variant: '#c4c6cd',
        },
        error: {
          DEFAULT: '#ba1a1a',
          container: '#ffdad6',
        },
        'on-error': '#ffffff',
        success: '#2d6a4f',
      },
    },
  },
}
```

With this in place, a card that today reads:

```css
background: var(--surface-container-lowest);
color: var(--on-surface);
```

becomes:

```html
<div class="bg-surface-container-lowest text-on-surface">
```

Tone variants (navy, emerald, gold, slate, crimson) can live as small utility combinations rather than dedicated classes, for example `bg-emerald-100 text-emerald-800` for the emerald tone, since Tailwind already ships a full emerald/amber/slate/rose scale that is close enough to the existing tints. Only the true brand colors (primary, secondary, surface scale) need to be custom; the tone accents can borrow Tailwind's built-in palettes to cut down on config size.

---

## 4. Typography

| Use | Current | Tailwind equivalent |
|---|---|---|
| Body, UI text | `Inter, -apple-system, system-ui, sans-serif` | `font-sans` (set as default) |
| Headlines, numbers, brand name | `Manrope, sans-serif` | `font-headline` (custom key) |

```js
// tailwind.config.js
theme: {
  extend: {
    fontFamily: {
      sans: ['Inter', '-apple-system', 'system-ui', 'sans-serif'],
      headline: ['Manrope', 'sans-serif'],
    },
  },
}
```

Notes on how headline type is used, worth preserving as conventions rather than one-off styles:

- Headlines use negative letter spacing at large sizes (roughly `-0.05em` to `-0.07em`). Tailwind's `tracking-tighter` (`-0.05em`) is close; for the biggest hero titles, an arbitrary value like `tracking-[-0.07em]` matches more precisely.
- Large display numbers (metrics, step numbers) are heavy weight (800) with tight tracking, same treatment as headlines.
- Eyebrow labels (small uppercase kickers) are `0.7 to 0.76rem`, weight 700 to 800, `letter-spacing: 0.12em to 0.14em`, uppercase. This maps directly to `text-xs font-bold uppercase tracking-widest`.

---

## 5. Spacing, radius, and elevation

### 5.1 Border radius scale

The system uses radius as a signal of hierarchy. Recommend standardizing on a small custom scale in Tailwind:

| Element type | Current px | Tailwind class |
|---|---|---|
| Small controls, chips, inputs | 8 to 12px | `rounded-lg` / `rounded-xl` |
| Icon wells, small badges | 10 to 14px | `rounded-xl` |
| Metric/insight cards | 16 to 22px | `rounded-2xl` |
| Section cards, panels | 22 to 28px | `rounded-[1.75rem]` (custom) |
| Hero panels, modals, large sections | 28 to 32px | `rounded-[2rem]` (custom) |
| Pills, tabs, badges | 999px | `rounded-full` |

Two custom radius keys are worth adding since Tailwind's default scale tops out at `rounded-3xl` (1.5rem):

```js
theme: {
  extend: {
    borderRadius: {
      '2.5xl': '1.75rem',
      '3.5xl': '2rem',
    },
  },
}
```

### 5.2 Shadows

The system avoids hard drop shadows in favor of soft, ambient ones:

```css
--shadow-lg: 0 40px 40px -10px rgba(25, 28, 28, 0.06);
--shadow-sm: 0 2px 12px rgba(25, 28, 28, 0.04);
```

```js
theme: {
  extend: {
    boxShadow: {
      'ambient-sm': '0 2px 12px rgba(25, 28, 28, 0.04)',
      'ambient-lg': '0 40px 40px -10px rgba(25, 28, 28, 0.06)',
      'brand': '0 2px 16px rgba(18, 40, 60, 0.18)',
      'hero': '0 30px 70px rgba(10, 25, 38, 0.16)',
    },
  },
}
```

Usage: `shadow-ambient-lg` on cards, `shadow-brand` on primary buttons, `shadow-hero` on the large gradient hero sections.

### 5.3 Gradients

The primary gradient (`135deg, #12283c 0%, #293e53 100%`) is used repeatedly on buttons, hero backgrounds, and icon wells. In Tailwind this becomes a utility combination rather than a token:

```html
<div class="bg-gradient-to-br from-primary to-primary-container">
```

For the more complex hero backgrounds that layer a radial highlight over the linear gradient, an arbitrary `bg-[image:...]` value or a small custom utility class in `@layer utilities` is the cleanest option, since Tailwind does not compose multiple background-image layers through simple utilities.

---

## 6. Component patterns

This section describes each recurring component as a set of Tailwind utility combinations, so it can be rebuilt without a separate stylesheet.

### 6.1 Buttons

Three variants exist: primary (gradient), secondary (flat neutral), tertiary (amber accent).

```html
<!-- Primary -->
<button class="inline-flex items-center justify-center gap-2 rounded-lg px-6 py-3
  bg-gradient-to-br from-primary to-primary-container text-on-primary
  font-semibold text-sm shadow-brand transition
  hover:opacity-90 hover:-translate-y-px active:scale-[0.98]
  disabled:opacity-50 disabled:cursor-not-allowed">
  Action
</button>

<!-- Secondary -->
<button class="inline-flex items-center justify-center gap-2 rounded-lg px-6 py-3
  bg-surface-container-high text-primary font-semibold text-sm
  transition hover:bg-surface-container">
  Action
</button>

<!-- Tertiary (accent) -->
<button class="inline-flex items-center justify-center gap-2 rounded-lg px-6 py-3
  bg-tertiary-fixed text-on-tertiary-fixed font-semibold text-sm shadow-ambient-sm
  transition hover:bg-tertiary-fixed-dim">
  Action
</button>
```

### 6.2 Cards

Base card: white surface, generous radius, ambient shadow, subtle hover shift to a slightly brighter surface.

```html
<div class="bg-surface-container-lowest rounded-xl p-6 shadow-ambient-lg
  transition-colors hover:bg-surface-bright">
  ...
</div>
```

### 6.3 Status chips and badges

```html
<span class="inline-flex items-center px-2.5 py-1 rounded-full text-[0.65rem]
  font-bold uppercase tracking-wide bg-secondary-container text-on-secondary-container">
  Completed
</span>
```

Error and running states swap the color pair only (`bg-error-container text-error`, `bg-surface-container-high text-on-surface-variant`).

### 6.4 Inputs

```html
<input class="w-full rounded-lg px-4 py-3 bg-surface-container-low text-on-surface
  placeholder:text-outline text-[0.9375rem] outline-none
  focus:ring-2 focus:ring-primary/30" />
```

Form labels use the eyebrow treatment: `text-xs font-semibold uppercase tracking-wide text-secondary mb-2 block`.

### 6.5 Sidebar navigation

```html
<aside class="w-60 h-screen bg-surface-container-low flex flex-col p-4 sticky top-0">
  <nav class="flex flex-col gap-1">
    <button class="flex items-center gap-2.5 w-full px-3.5 py-2.5 rounded-lg
      text-sm font-medium text-secondary transition
      hover:bg-surface-container hover:text-on-surface">
      Dashboard
    </button>
    <!-- active state -->
    <button class="flex items-center gap-2.5 w-full px-3.5 py-2.5 rounded-lg
      text-sm font-semibold text-primary bg-surface-container-lowest shadow-ambient-sm">
      Reports
    </button>
  </nav>
</aside>
```

### 6.6 Tables

Header rows use a very light gradient tint, body rows get a hover tint, and there is a distinct "editing" row state.

```html
<table class="w-full border-collapse text-sm">
  <thead>
    <tr class="bg-gradient-to-b from-surface-container to-surface-container-low">
      <th class="px-4 py-3 text-xs font-bold uppercase tracking-wide text-secondary
        text-left border-b border-surface-container-high">Column</th>
    </tr>
  </thead>
  <tbody>
    <tr class="hover:bg-primary/[0.025]">
      <td class="px-4 py-3.5 border-b border-surface-container-high/60">Value</td>
    </tr>
    <!-- editing row -->
    <tr class="bg-primary/[0.06]">...</tr>
  </tbody>
</table>
```

### 6.7 Modals

```html
<div class="fixed inset-0 flex items-center justify-center p-4
  bg-black/45 backdrop-blur-md">
  <div class="bg-surface-container-lowest rounded-3xl p-6 shadow-ambient-lg max-w-md w-full">
    ...
  </div>
</div>
```

### 6.8 Chat bubbles

```html
<!-- User -->
<div class="max-w-[82%] self-end px-4 py-2.5 rounded-xl rounded-br-sm text-sm leading-relaxed
  bg-gradient-to-br from-primary to-primary-container text-on-primary">
  Message
</div>

<!-- Agent -->
<div class="max-w-[82%] self-start px-4 py-2.5 rounded-xl rounded-bl-sm text-sm leading-relaxed
  bg-surface-container-low text-on-surface">
  Message
</div>
```

---

## 7. Page-level patterns

These are higher-order layouts built from the components above. They are documented here as composition patterns, not new tokens.

### 7.1 Admin dashboard

- A hero band with a dark navy gradient, a radial amber highlight in one corner, and a decorative blurred circle, containing a title, subtitle, actions, and 2 to 3 "insight cards" with light text on the dark background.
- Below it, a metrics grid (4 columns down to 1 on mobile) of cards pairing an icon well with a large number and a caption.
- Tone variants (navy, emerald, gold, slate, crimson) recolor the icon well and headline text only, everything else stays consistent.
- Collapsible "section cards" containing tables, each with a toggleable header (icon, title, subtitle, meta) and a bordered body.
- An "add row" bar above each table for inline record creation.

In Tailwind, the hero's layered background is the one place worth a small custom utility (`@layer utilities { .bg-hero { ... } }`) rather than trying to force it into inline arbitrary values, since it stacks a radial and a linear gradient.

### 7.2 Landing page

Composed from a repeating rhythm of "sections": a rounded, semi-transparent, blurred panel (`bg-white/70 backdrop-blur-lg border border-primary/10 shadow-ambient-lg rounded-3xl p-10`), each containing one thematic block:

- Hero: two-column grid, large negative-tracking headline on the left, a feature panel on the right.
- Contrast statement: centered, large, mixed-weight sentence.
- Pillars / use cases / steps: repeating grids of small icon and text cards (3 or 4 columns collapsing to 1).
- Modes: two-column feature cards with numbered badges.
- Sample reports: tabbed interface with stat panels colored by outcome (ok, warn, danger, neutral) using green, amber, red, and neutral tints.
- Waitlist / CTA: two-column form beside benefit copy, or a centered closing statement.
- Footer: centered, minimal.

This translates cleanly to Tailwind's grid and responsive utilities (`grid grid-cols-3 md:grid-cols-2 sm:grid-cols-1 gap-4`), with the frosted-glass panel look coming from `bg-white/70 backdrop-blur-md`.

### 7.3 Auth pages

A two-column split below 900px collapsing to one column: a "story" panel (brand recap, highlights, trust metrics) beside a form panel with a mode switch (login/signup), status banners (success/warning/error, each a tinted rounded box), and inputs. Password fields get a left-aligned icon inset via `pl-11` with an absolutely positioned icon.

---

## 8. Responsive breakpoints

Current custom breakpoints map closely to Tailwind's defaults; recommend using Tailwind's standard scale rather than the exact pixel values, since they are already close:

| Current | Nearest Tailwind breakpoint |
|---|---|
| 1180px | `xl` (1280px) or a custom `lg2: 1180px` if pixel-parity matters |
| 860px | `md` (768px), or custom `tablet: 860px` |
| 640px | `sm` (640px), exact match |

If pixel-parity with the current design matters more than convention, add the two custom breakpoints:

```js
theme: {
  extend: {
    screens: {
      tablet: '860px',
      wide: '1180px',
    },
  },
}
```

Otherwise, simplify to Tailwind's `sm`, `md`, `lg` and accept the small shifts, which keeps the config smaller and easier to maintain going forward.

---

## 9. Migration approach

1. Start the Tailwind config with the color, font, radius, and shadow extensions in sections 3 to 5. This alone recreates the visual identity.
2. Rebuild components (buttons, cards, chips, inputs, nav items) as either plain utility strings or, if reused often, as `@layer components` classes (e.g. `.btn-primary`) so markup stays readable.
3. Rebuild page-level layouts using Tailwind's grid and flex utilities, matching the column counts and breakpoints in section 8.
4. For the few backgrounds that layer multiple gradients (hero bands), keep a very small number of custom utility classes in `@layer utilities` rather than fighting Tailwind's single-background-image limitation with arbitrary values.
5. Retire the hand-written CSS file once all components have Tailwind equivalents; keep this document as the reference for anyone extending the system later.

---

## 10. Summary

The visual identity here does not require a heavy custom stylesheet, it requires a well-configured Tailwind theme (colors, two font families, an extended radius scale, four shadow tokens) plus a small, consistent set of utility combinations for buttons, cards, chips, inputs, and layout grids. Everything else in the current CSS is composition of those same primitives repeated across pages.
