# Agent Exports

This directory contains public package artifacts and generated export copies.

Installed-package consumers should resolve these files from:

- `@partnerdevops/partner-components/agent-artifacts/exports/<public-file>`

Public files include:

- `component-catalog.json`
- `component-examples.json`
- `design-tokens.json`
- `figma-component-map.json`
- `figma-mapping-hints.json`
- `ai-artifacts.md`

Repo-local only files include:

- `component-catalog.generated.json`
- `component-catalog.annotations.json`
- `component-examples.generated.json`
- `component-examples.annotations.json`

Curated Figma source files live outside this directory in:

- `agent-artifacts/source/figma-component-map.json`
- `agent-artifacts/source/figma-mapping-hints.json`

The canonical contract document and curated Figma files are copied into this directory during artifact sync and package builds.
