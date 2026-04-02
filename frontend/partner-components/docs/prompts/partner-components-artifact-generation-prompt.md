# LLM Prompt: Generate Partner Components Agent Artifacts

Use this prompt when the deterministic artifact exports need to be regenerated from repository source files.

```md
You are updating machine-readable repository artifacts so AI agents can consistently implement Vue 3 UI with `@partnerdevops/partner-components`.

## Objective
Refresh the deterministic artifact outputs and supporting guidance so agents can discover:

- what components exist
- how they are imported
- which examples exist in Storybook
- which tokens are available

## Source Of Truth (read first)
1. `src/index.ts` for public exports
2. `src/components/**` for component source files
3. `src/components/**/*.stories.ts` for story names, args, and canonical example snippets from `parameters.exportableCode` when present
4. `tests/*.spec.ts` for linked test coverage
5. `src/styles/*.css` for design tokens
6. `docs/ai-artifacts.md` for generated vs curated ownership rules
7. `agent-artifacts/schemas/*.schema.json` for required output shapes
8. `scripts/generate-agent-artifacts.mjs` for the current deterministic extraction behavior

## Files To Update
1. `agent-artifacts/exports/component-catalog.generated.json`
2. `agent-artifacts/exports/component-catalog.json`
3. `agent-artifacts/exports/component-examples.generated.json`
4. `agent-artifacts/exports/component-examples.json`
5. `agent-artifacts/exports/design-tokens.json`
6. `README.md` only when artifact workflow references need adjustment
7. `docs/ai-artifacts.md` only when the contract changes
8. `scripts/generate-agent-artifacts.mjs` if the deterministic parser needs to improve

## Required Rules
1. Keep deterministic extraction separate from interpretation.
2. Only place directly observable facts in generated outputs.
3. Do not overwrite or hallucinate curated guidance fields.
4. Do not invent props, slots, emits, stories, tokens, or exports that are not present in the repository.
5. If a field cannot be derived safely, leave it absent from generated output and capture it in the enrichment pass instead.
6. Keep import names and paths aligned with current exports in `src/index.ts`.
7. Ensure final generated outputs validate against `agent-artifacts/schemas/`.

## Out Of Scope

Do not author or substantially rewrite:

- `component-catalog.annotations.json`
- `component-examples.annotations.json`
- `agent-artifacts/source/figma-component-map.json`
- `agent-artifacts/source/figma-mapping-hints.json`

Those files belong to the enrichment workflow.

## Acceptance Criteria
1. An agent can enumerate public Partner components without reading Storybook UI.
2. An agent can retrieve story examples and args in a structured format.
3. Tokens are available as machine-readable data, not only CSS files.
4. Generated facts remain clearly separated from curated guidance.
5. Final generated outputs validate against the schemas in `agent-artifacts/schemas/`.

## Output Format
1. Apply edits directly to files.
2. Run:
   - `npm run agent-artifacts:generate`
   - `npm run agent-artifacts:validate`
3. Provide a short summary:
   - What changed
   - Any extraction gaps that still need enrichment or parser work
```
