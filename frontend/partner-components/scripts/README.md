# Scripts

Utility scripts for the partner-components project.

## clean-svg-colors.cjs

Removes hardcoded colors from SVG files and replaces them with `currentColor` to make them work properly with CSS styling.

### Usage

#### Via npm scripts (recommended):

Process all icon directories:

```bash
npm run icons:clean
```

Process specific directories:

```bash
npm run icons:clean-outline
npm run icons:clean-solid
```

#### Direct script execution:

Process all icon directories (default):

```bash
node scripts/clean-svg-colors.cjs
```

Process a specific directory:

```bash
node scripts/clean-svg-colors.cjs src/assets/icons/outline
node scripts/clean-svg-colors.cjs src/assets/icons/solid
node scripts/clean-svg-colors.cjs path/to/new/icons
```

### What it does

- **Replaces hardcoded colors** like `#858B91`, `#000000`, `rgb(133,139,145)` with `currentColor`
- **Preserves white colors** (`#FFFFFF`, `white`) for internal details in solid icons
- **Preserves transparent values** (`fill="none"`, `stroke="none"`)
- **Handles various color formats**: 6-digit hex, 3-digit hex, RGB, named colors

### When to use

- When adding new SVG icons with hardcoded colors
- When icons appear as filled circles or don't respond to color changes
- As part of icon preparation workflow

### Example transformation

**Before:**

```svg
<path stroke="#858B91" fill="#858B91" />
```

**After:**

```svg
<path stroke="currentColor" fill="currentColor" />
```
