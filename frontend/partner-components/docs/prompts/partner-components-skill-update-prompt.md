# LLM Prompt: Update Partner Components AI Artifacts

This file now serves as a pointer to the split prompt workflow:

- Deterministic generation: [partner-components-artifact-generation-prompt.md](partner-components-artifact-generation-prompt.md)
- LLM enrichment: [partner-components-artifact-enrichment-prompt.md](partner-components-artifact-enrichment-prompt.md)

Use the generation prompt when you need to refresh repository-derived facts.

Use the enrichment prompt when you need to improve curated annotations, tags, usage guidance, or Figma mapping hints.

For exportable example snippets, prefer defining canonical code directly in each component's `Default` story via `parameters.exportableCode`, then let deterministic artifact generation extract that value. Do not rely on Storybook-only render scaffolding, `v-for` galleries, configuration iteration, or mock-data loops when producing exportable examples.
