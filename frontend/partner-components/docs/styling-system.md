# Partner Components Styling System

This document explains how the Partner Components library styles are structured and how they integrate with Tailwind CSS v4 and ShadCN Vue.

## Architecture Overview

The styling system is built on three layers:

1. **Partner Design Tokens** — CSS custom properties (`--partner-*`) defining the brand's color palette, spacing, shadows, radii, typography, and breakpoints
2. **Tailwind CSS v4 Theme** — Partner tokens mapped into Tailwind's `@theme` system, enabling standard Tailwind utility classes (e.g., `bg-primary-600`) backed by Partner values
3. **ShadCN Vue Semantic Variables** — A bridge layer that maps Partner tokens to ShadCN's expected variable names (`--background`, `--foreground`, `--primary`, etc.) so ShadCN components render with Partner colors

### Import Chain

```
global.css
├── tailwind.css
│   ├── tailwindcss          (Tailwind v4 core)
│   ├── tailwindcss-animate   (animation plugin)
│   └── shadcn.css            (ShadCN theme variables + Tailwind theme overrides)
├── colors.css               (Partner→Tailwind color mapping + ShadCN semantic overrides)
│   └── partner-colors.css   (Foundation palette + utility classes)
├── partner-spacing.css
├── partner-radius.css
├── partner-shadows.css
├── partner-breakpoints.css
└── partner-typography.css
```

Consuming apps import the library's styles via:

```typescript
import '@partnerdevops/partner-components/dist/style.css'
```

## Style Files

### `partner-colors.css` — Foundation Palette

Defines the raw color values as CSS custom properties under `:root`. These are the single source of truth for all colors.

**Color families** (10 shades each, numbered 1–10, light to dark):

| Family | Variable prefix | Role |
|---|---|---|
| Charcoal Gray | `--partner-gray-*` | Text, borders, neutral elements |
| Partner Blue | `--partner-blue-*` | Primary brand color |
| Partner Orange | `--partner-orange-*` | Secondary brand color |
| Red | `--partner-red-*` | Error / destructive states |
| Yellow | `--partner-yellow-*` | Warning states |
| Green | `--partner-green-*` | Success states |

**Semantic tokens** map the raw shades to roles:

```css
/* Primary (blue) */
--partner-primary: var(--partner-blue-7);
--partner-primary-main: var(--partner-blue-7);
--partner-primary-dark: var(--partner-blue-8);
--partner-primary-light: var(--partner-blue-6);
--partner-primary-contrast: var(--partner-white);

/* Text */
--partner-text-primary: var(--partner-gray-7);
--partner-text-secondary: var(--partner-gray-6);
--partner-text-disabled: var(--partner-gray-5);

/* Border */
--partner-border-default: var(--partner-gray-5);
--partner-border-light: var(--partner-gray-2);
--partner-border-active: var(--partner-blue-7);

/* Fill */
--partner-fill-hover: var(--partner-gray-1);
--partner-fill-selected: var(--partner-blue-1);

/* Background */
--partner-background-white: var(--partner-white);
--partner-background-gray: var(--partner-gray-1);
```

The same file also provides **utility classes** as a `@layer utilities` block:

```css
/* Text color */
.text-partner-primary    →  var(--partner-text-primary)
.text-partner-secondary  →  var(--partner-text-secondary)
.text-partner-gray-1     →  var(--partner-gray-1)   /* through gray-10 */
.text-partner-blue-1     →  var(--partner-blue-1)    /* through blue-10 */
/* ... same pattern for orange, red, yellow, green */

/* Background color */
.bg-partner-primary      →  var(--partner-primary)
.bg-partner-gray-1       →  var(--partner-gray-1)    /* through gray-10 */
.bg-partner-blue-1       →  var(--partner-blue-1)     /* through blue-10 */
/* ... same pattern for orange, red, yellow, green */
```

This also contains a **PowerBI** color palette for data visualization scales.

### `colors.css` — Tailwind + ShadCN Color Mapping

Maps Partner's 1–10 shade scale onto Tailwind's 50–900 scale using `@theme inline`:

```css
@theme inline {
  --color-primary-50: var(--partner-blue-1);    /* lightest */
  --color-primary-100: var(--partner-blue-2);
  --color-primary-200: var(--partner-blue-3);
  /* ... */
  --color-primary-900: var(--partner-blue-10);  /* darkest */
}
```

This enables standard Tailwind color classes:

```html
<div class="bg-primary-600 text-primary-50">Partner Blue</div>
<div class="bg-success-500 text-white">Green</div>
<div class="text-gray-600">Charcoal text</div>
```

Available Tailwind color scales: `primary`, `secondary`, `gray`, `orange`, `red`, `yellow`, `green`, `blue`, `success`.

This file also overrides ShadCN's semantic variables so they resolve to Partner tokens:

```css
:root {
  --background: var(--partner-background-white);
  --foreground: var(--partner-text-primary);
  --primary: var(--partner-primary-main);
  --destructive: var(--partner-error-main);
  --border: var(--partner-border-light);
  --ring: var(--partner-blue-6);
  /* ... card, popover, muted, accent, sidebar, chart-1 through chart-5 */
}
```

### `partner-radius.css` — Border Radius

```css
--partner-radius-none: 0rem;       /* Tables, grids */
--partner-radius-xs:   0.0625rem;  /* 1px */
--partner-radius-sm:   0.125rem;   /* 2px — Buttons, inputs, tooltips */
--partner-radius-md:   0.25rem;    /* 4px — Cards, small popups */
--partner-radius-lg:   0.5rem;     /* 8px — Larger modals */
--partner-radius-xl:   0.75rem;    /* 12px */
--partner-radius-2xl:  1rem;       /* 16px */
--partner-radius-3xl:  1.5rem;     /* 24px */
--partner-radius-full: 9999px;     /* Chips, avatars */
```

Integrated into Tailwind via `@theme`, so standard classes work: `rounded-sm`, `rounded-md`, `rounded-lg`, etc.

### `partner-shadows.css` — Elevation

```css
--partner-shadow-none: none;
--partner-shadow-sm: 0px 1px 4px rgba(0, 0, 0, 0.16);
--partner-shadow-md: 0px 2px 8px rgba(0, 0, 0, 0.20);
--partner-shadow-lg: 0px 4px 12px rgba(0, 0, 0, 0.24);
```

Includes dark mode variants with inverted (white) shadow colors. Standard Tailwind classes apply: `shadow-sm`, `shadow-md`, `shadow-lg`.

### `partner-spacing.css` — Spacing

Tailwind v4's default spacing scale is used directly (linear: `--spacing` defaults to `0.25rem`, so `p-4` = `1rem`). One additional token is defined:

```css
--partner-spacing-half: calc(var(--spacing, 0.25rem) / 2);  /* 2px */
```

Use via: `p-(--partner-spacing-half)` or `p-[0.125rem]`.

### `partner-breakpoints.css` — Responsive Layout

Custom breakpoints registered in Tailwind's `@theme`:

| Breakpoint | Width | Columns | Gutters | Margins |
|---|---|---|---|---|
| `sm` | 0px | 8 | 24px | 24px |
| `md` | 1024px | 12 | 24px | 32px |
| `lg` | 1440px | 12 | 32px | 32px |
| `xl` | 1920px | 12 | 32px | 64px |

Responsive prefixes work as expected: `sm:`, `md:`, `lg:`, `xl:`.

Layout properties (columns, gutters, margins) are available as CSS variables for custom grid implementations:

```css
gap: var(--partner-breakpoint-md-gutters);
```

### `partner-typography.css` — Type Scale

CSS classes based on the Figma design system. Font family: **Roboto**.

| Class | Weight | Size | Line height | Use case |
|---|---|---|---|---|
| `.partner-h1` | Light (300) | 54px | 56px | Page titles |
| `.partner-h2` | Light (300) | 32px | 34px | Section headings |
| `.partner-h3` | Light (300) | 24px | 28px | Subsection headings |
| `.partner-h4` | Regular (400) | 18px | 24px | Card headings |
| `.partner-h5` | Semibold (600) | 16px | 22px | Small headings |
| `.partner-h6` | Semibold (600) | 14px | 20px | Smallest heading |
| `.partner-headline1` | Semibold (600) | 14px | 20px | Bold label |
| `.partner-headline2` | Semibold (600) | 12px | 20px | Small bold label |
| `.partner-headline3` | Medium (500) | 12px | 20px | Medium label |
| `.partner-body1` | Regular (400) | 14px | 20px | Default body text |
| `.partner-body2` | Regular (400) | 12px | 18px | Small body text |
| `.partner-buttonLarge` | Medium (500) | 16px | 22px | Large buttons |
| `.partner-buttonMedium` | Medium (500) | 14px | 20px | Medium buttons |
| `.partner-buttonSmall` | Medium (500) | 12px | 20px | Small buttons |
| `.partner-inputText` | Regular (400) | 14px | 20px | Input fields |
| `.partner-inputLabel` | Regular (400) | 12px | 14px | Form labels |
| `.partner-helperText` | Regular (400) | 11px | 16px | Helper / error text |
| `.partner-subhead` | Regular (400) | 10px | 16px | Uppercase subheads |
| `.partner-tooltip` | Regular (400) | 10px | 16px | Tooltip text |

Aliases are available for convenience (e.g., `.partner-body-1`, `.partner-subtitle-1`, `.partner-button-large`).

### `shadcn.css` — ShadCN Vue Integration

Generated by the ShadCN Vue initializer. Defines ShadCN's expected semantic variables in OKLCH format and registers them in Tailwind's theme via `@theme inline`. The values in this file are **overridden** by `colors.css` to use Partner tokens instead, so the OKLCH fallbacks only apply if `colors.css` is not loaded.

Also applies base styles:

```css
@layer base {
  * { @apply border-border outline-ring/50; }
  body { @apply bg-background text-foreground; }
}
```

## Dark Mode

Dark mode is activated by adding either the `.dark` class or the `data-mode="dark"` attribute to a parent element.

Files that include dark mode overrides:
- `partner-colors.css` — flips semantic tokens (e.g., `--partner-primary` changes from blue-7 to blue-4)
- `partner-shadows.css` — inverts shadow colors to white-based
- `colors.css` — overrides ShadCN semantic variables for dark backgrounds

## How Components Use Styles

Components in this library follow a consistent pattern:

1. **CVA (class-variance-authority)** for variant-based class management
2. **`cn()` utility** (from `src/lib/utils.ts`) to merge Tailwind classes — uses `clsx` + `tailwind-merge`
3. **Tailwind utility classes** referencing Partner tokens via the `@theme` mappings
4. **Tailwind arbitrary value syntax** for direct CSS variable access: `bg-(--partner-primary-main)`
5. **ShadCN base components** in `src/components/shadcn/ui/` wrapped by Partner components (e.g., `PButton` wraps ShadCN's `Button`)

Example from a component:

```html
<button :class="cn(
  buttonVariants({ variant: 'primary', appearance: 'fill', size: 'medium' }),
  props.class
)">
  <slot />
</button>
```

## Using Styles in Consuming Apps

### Partner utility classes

```html
<!-- Text colors -->
<p class="text-partner-primary">Primary text</p>
<p class="text-partner-blue-7">Partner Blue</p>

<!-- Background colors -->
<div class="bg-partner-gray-1">Light gray background</div>

<!-- Typography -->
<h1 class="partner-h1">Page Title</h1>
<p class="partner-body1">Body text</p>
```

### Tailwind classes (backed by Partner tokens)

```html
<div class="bg-primary-600 text-white rounded-md shadow-md p-4">
  Content styled with Partner tokens via Tailwind
</div>
```

### ShadCN semantic classes

```html
<div class="bg-background text-foreground border-border">
  Automatically uses Partner colors
</div>
```

### Direct CSS variable access

```css
.custom-element {
  color: var(--partner-text-primary);
  background: var(--partner-blue-1);
  border-radius: var(--partner-radius-md);
  box-shadow: var(--partner-shadow-sm);
}
```

Or via Tailwind's arbitrary value syntax:

```html
<div class="bg-(--partner-fill-selected) text-(--partner-text-primary)">
  Custom token access
</div>
```
