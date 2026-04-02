# Partner Components

A Vue 3 component library that provides wrapper components around shadcn-vue components with additional functionality, consistent styling, and enhanced developer experience.

## Features

- 🎨 **Consistent Design System** - Built on top of shadcn-vue and Tailwind CSS with Partner-specific styling
- 📝 **TypeScript Support** - Full TypeScript definitions for all components
- 📦 **Tree Shaking** - Only import what you need
- 🚀 **Vue 3 Compatible** - Built with Vue 3 Composition API

## Storybook

Our hosted Storybook of all components is available at [https://www.partner-components.com/](https://www.partner-components.com/). Password is required, please ask a Partner developer for access.

## Installation

### Prerequisites

To install this package from GitHub Packages, you need to authenticate with npm. Create a `.npmrc` file in your project root (or in your home directory `~/.npmrc`) with the following content:

```
@partnerdevops:registry=https://npm.pkg.github.com
//npm.pkg.github.com/:_authToken=${NPM_TOKEN}
```

Replace `NPM_TOKEN` with a GitHub Personal Access Token (PAT) that has the `read:packages` permission. You can create a token at [GitHub Settings > Developer settings > Personal access tokens](https://github.com/settings/tokens).

Alternatively, you can use an environment variable:

```bash
export NPM_TOKEN=your_github_personal_access_token_here
```

### Install the Package

```bash
npm install @partnerdevops/partner-components
```

The components import styles themselves, so you don't need to import anything else. If you want to use the styles outside of the component library, you can do so by importing the component library's CSS file:

```css
@import '@partnerdevops/partner-components/dist/style.css';
```

## Quick Start

```vue
<template>
  <div class="space-y-4">
    <PSearchBar
      v-model="query"
      placeholder="Search users"
      @search="runSearch"
    />

    <PButton @click="refresh">Refresh</PButton>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { PButton, PSearchBar } from '@partnerdevops/partner-components'

const query = ref('')

function runSearch(value: string) {
  query.value = value
}

function refresh() {
  runSearch(query.value)
}
</script>
```

## Usage Guidance

- Prefer exported `P*` components before building custom UI.
- Compose existing components before introducing wrappers.
- Use library tokens and token-backed utility classes instead of hard-coded visual values.
- Validate behavior, emits, and accessibility states with focused Vitest browser tests.

For machine-readable AI integration guidance, see [docs/ai-artifacts.md](docs/ai-artifacts.md).

Installed-package consumers should resolve artifacts from the published package surface:

- `@partnerdevops/partner-components/agent-artifacts/exports/component-catalog.json`
- `@partnerdevops/partner-components/agent-artifacts/exports/component-examples.json`
- `@partnerdevops/partner-components/agent-artifacts/exports/design-tokens.json`
- `@partnerdevops/partner-components/agent-artifacts/exports/figma-component-map.json`
- `@partnerdevops/partner-components/agent-artifacts/exports/figma-mapping-hints.json`
- `@partnerdevops/partner-components/agent-artifacts/exports/ai-artifacts.md`

Published schemas live under `@partnerdevops/partner-components/agent-artifacts/schemas/*`.

## Development

To explore all components and their variants, run Storybook:

```bash
npm run storybook
```

This will start Storybook on `http://localhost:6006` where you can:

- Browse all components and their variants
- Interact with components in real-time
- View component documentation
- Test different props and states

## Components

The following components are available:

- PAlert
- PAvatar, PAvatarGroup
- PBadge
- PButton
- PCalendar, PDateInput *(uses Luxon `DateTime` for v-model)*
- PCheckbox, PCheckboxGroup
- PChip
- PDialog, PDialogClose
- PIcon
- PLabel
- PLayout, PLayoutGrid, PLayoutGridItem
- PLogo
- PMenu, PMenuItem, PSelectMenu
- PNumericInput
- POverflowGroup
- PPagination, PPaginationContent, PPaginationEllipsis, PPaginationFirst, PPaginationItem, PPaginationLast, PPaginationNext, PPaginationPrevious, PPaginationRoot
- PPopover
- PRadioGroup
- PSearchBar
- PSelect
- PSwitch
- PTable, PTableBody, PTableCaption, PTableCell, PTableEmpty, PTableFooter, PTableHead, PTableHeader, PTableRow
- PTextArea
- PTextInput
- PToast *(uses `showToast()` utility for triggering)*
- PTooltip
- PTypography

## Development

### Setup

```bash
# Install dependencies
npm install

# Start Storybook for development
npm run storybook

# Build library
npm run build

# Build Storybook for deployment
npm run build-storybook

# Type checking
npm run type-check

# Linting
npm run lint

# Testing
npm run test
```

### Project Structure

```
src/
├── components/         # Vue components and Storybook stories
├── composables/        # Shared Vue composition helpers
├── lib/                # Library utilities
├── styles/             # Global styles and token mappings
├── types/              # Shared TypeScript types
├── utils/              # Shared utilities
└── index.ts            # Main entry point
```

## Publishing

This package is published to GitHub Packages. To publish a new version:

### Manual Publishing

1. Ensure you have a GitHub Personal Access Token with `write:packages` permission
2. Set the `NPM_TOKEN` environment variable:
   ```bash
   export NPM_TOKEN=your_github_token_here
   ```
3. Build the package:
   ```bash
   npm run build
   ```
4. Publish:
   ```bash
   npm publish
   ```

`npm publish` runs `prepack`, which regenerates the deterministic AI artifacts and then builds the package so the published contents stay aligned with source.

### Automated Publishing via GitHub Actions

The package is automatically published when a version tag is pushed:

1. Update the version in `package.json`
2. Commit and push your changes
3. Create and push a version tag:
   ```bash
   git tag v1.0.1
   git push origin v1.0.1
   ```

The GitHub Actions workflow will automatically build and publish the package to GitHub Packages.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

ISC License - see LICENSE file for details.

## Support

For support and questions, please contact Partner Engineering & Science, Inc.
