# Partner Components AI Artifacts

`@partnerdevops/partner-components` publishes agent-readable design-system artifacts as part of the package distribution. These artifacts are public consumable outputs, intended for downstream skills, code generators, and design-to-code workflows.

## Public Install-Time Path

Consumers should treat the installed-package path below as the stable contract:

- `@partnerdevops/partner-components/agent-artifacts/exports/component-catalog.json`
- `@partnerdevops/partner-components/agent-artifacts/exports/component-examples.json`
- `@partnerdevops/partner-components/agent-artifacts/exports/design-tokens.json`
- `@partnerdevops/partner-components/agent-artifacts/exports/figma-component-map.json`
- `@partnerdevops/partner-components/agent-artifacts/exports/figma-mapping-hints.json`
- `@partnerdevops/partner-components/agent-artifacts/exports/ai-artifacts.md`

The package also publishes JSON Schemas at:

- `@partnerdevops/partner-components/agent-artifacts/schemas/component-catalog.schema.json`
- `@partnerdevops/partner-components/agent-artifacts/schemas/component-examples.schema.json`
- `@partnerdevops/partner-components/agent-artifacts/schemas/design-tokens.schema.json`
- `@partnerdevops/partner-components/agent-artifacts/schemas/figma-component-map.schema.json`
- `@partnerdevops/partner-components/agent-artifacts/schemas/figma-mapping-hints.schema.json`

Repo-local source files live under `agent-artifacts/exports/`, `agent-artifacts/source/`, and `agent-artifacts/schemas/`. The installed-package paths above are the ones downstream consumers should code against.

The package does not publish repo-local intermediate artifacts such as `*.generated.json` or `*.annotations.json`. Those remain development-time files in this repository only.

## Artifact Contract

### `component-catalog.json`

Merged, agent-facing component inventory. This is the primary entry point for discovering public Partner components, their props, emits, slots, variants, stories, tests, and curated usage guidance.

### `component-examples.json`

Merged examples catalog derived from Storybook stories plus curated annotations. Use this when an agent needs example args, story IDs, and code snippets tied to real library examples.

For downstream code generation, treat the `Default` story as the preferred source for the canonical exportable example when `parameters.exportableCode` is present in the story file. This explicit snippet should override raw Storybook render-template extraction when the rendered story uses gallery loops, config iteration, mock data, or other demo-only scaffolding that is not appropriate for direct application usage.

### `design-tokens.json`

Deterministic token export derived from `src/styles`. Use this for token lookup, CSS variable discovery, and style-system reasoning.

### `figma-component-map.json`

Curated registry of canonical Figma nodes that map to Partner components or planned components. Use this when grounding a Figma selection against a known Partner component.

### `figma-mapping-hints.json`

Curated pattern-to-component translation hints. Use this when the Figma design uses pattern names or variant labels that need to be interpreted into Partner component choices and prop values.

### `ai-artifacts.md`

Human-readable and machine-readable contract documentation for downstream consumers. This file describes artifact purpose, ownership, generation flow, and stability expectations.

## Source Of Truth And Ownership

The artifacts use a split ownership model so deterministic facts stay generated and curated guidance stays reviewable.

### Generated sources of truth

Generated fields come from repository sources and should be regenerated rather than edited by hand:

- `src/index.ts`
  - public export names
  - package import metadata
- `src/components/**/*.vue`
  - component source references
  - props, emits, slots, and defaults where extraction is reliable
- `src/components/**/*.stories.ts`
  - story names
  - story IDs
  - story args
  - canonical exportable snippets from `parameters.exportableCode`
  - otherwise, directly declared render templates when no canonical exportable snippet exists
- `tests/*.spec.ts`
  - linked behavior coverage by component
- `src/styles/*.css`
  - token names
  - CSS variables
  - token values

### Curated sources of truth

Curated files are intentionally maintained and reviewed:

- `agent-artifacts/exports/component-catalog.annotations.json`
- `agent-artifacts/exports/component-examples.annotations.json`
- `agent-artifacts/source/figma-component-map.json`
- `agent-artifacts/source/figma-mapping-hints.json`

Curated content includes:

- usage guidance
- semantic tags
- accessibility notes
- composition recommendations
- Figma alignment notes
- ambiguity rules
- fallback rules

If a value should be deterministically derivable from source, improve the generator instead of editing the merged artifact manually.

## Repo-Local Only Files

These files exist in the repository to support generation, review, and auditing, but they are not part of the installed package contract:

- `agent-artifacts/exports/component-catalog.generated.json`
- `agent-artifacts/exports/component-catalog.annotations.json`
- `agent-artifacts/exports/component-examples.generated.json`
- `agent-artifacts/exports/component-examples.annotations.json`
- `agent-artifacts/source/figma-component-map.json`
- `agent-artifacts/source/figma-mapping-hints.json`

## Generation And Enrichment Workflow

The intended workflow is:

1. Deterministic generation
   - `npm run agent-artifacts:generate`
   - Refreshes generated artifacts from code, stories, tests, and tokens.
2. Contract sync and validation
   - `npm run agent-artifacts:prepare`
   - Copies this contract into `agent-artifacts/exports/ai-artifacts.md`, copies curated Figma sources into `agent-artifacts/exports/`, and validates required artifacts and schemas.
3. Full update
   - `npm run agent-artifacts:update`
   - Runs generation and then prepare.

Normal local development does not need to regenerate artifacts on every command. The standard build validates and syncs the existing artifact set, while package creation regenerates before packaging:

- `npm run build`
  - runs `agent-artifacts:prepare`
  - builds the library
- `npm pack` or `npm publish`
  - triggers `prepack`
  - runs deterministic generation and the normal build before creating the distributable package

This keeps day-to-day development lighter while ensuring published packages carry refreshed, validated artifacts.

## Stability Expectations

- The install-time base path `agent-artifacts/exports/` is intended to remain stable for downstream consumers.
- Artifact filenames listed in this document are public and should be treated as part of the package contract.
- JSON file shapes are governed by the published schemas in `agent-artifacts/schemas/`.
- Each artifact includes `schemaVersion` and `generatedAt`.
- Backward-incompatible schema changes should be explicit and versioned rather than silently changing field shapes.

Generated timestamps may change between releases even when structural data does not. Consumers should not use `generatedAt` as a semantic change detector.

## Downstream Consumer Guidance

Downstream skills and agents should:

- resolve artifacts from the installed package path, not from repo-local copies
- prefer merged artifacts (`component-catalog.json`, `component-examples.json`) over `*.generated.json`
- use published schemas when validating JSON consumption
- treat `figma-component-map.json` and `figma-mapping-hints.json` as curated guidance, not guaranteed exhaustive truth

If a consumer needs the contract doc itself, read:

- `@partnerdevops/partner-components/agent-artifacts/exports/ai-artifacts.md`

## Figma Source Of Truth

The current master Figma design-system file for artifact enrichment is:

- File key: `1IqfGdn5XxqnBm3CZ5rFH1`
- URL: `https://www.figma.com/design/1IqfGdn5XxqnBm3CZ5rFH1/Partner_Master-Design-System_V2_10162025?m=dev`

Use this file as the default grounding source for:

- component naming alignment
- design-token verification
- layer-name and pattern mapping guidance

The grounded component registry is stored in:

- `agent-artifacts/source/figma-component-map.json`

## Artifact Inventory In This Repo

The repo-local artifact workspace contains:

- `agent-artifacts/exports/component-catalog.generated.json`
- `agent-artifacts/exports/component-catalog.annotations.json`
- `agent-artifacts/exports/component-catalog.json`
- `agent-artifacts/exports/component-examples.generated.json`
- `agent-artifacts/exports/component-examples.annotations.json`
- `agent-artifacts/exports/component-examples.json`
- `agent-artifacts/exports/design-tokens.json`
- `agent-artifacts/exports/ai-artifacts.md`
- `agent-artifacts/source/figma-component-map.json`
- `agent-artifacts/source/figma-mapping-hints.json`

The primary public subset for downstream consumers is the merged outputs plus this contract document and the published schemas. The generated, annotation, and curated source files remain repo-local because they are useful for debugging, audits, authoring, and future tooling, but they are not part of the package surface.
