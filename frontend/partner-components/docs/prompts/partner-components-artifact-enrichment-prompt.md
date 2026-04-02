# LLM Prompt: Enrich Partner Components Agent Artifacts

Use this prompt after the deterministic artifacts have been generated and validated. This prompt is for adding system knowledge that cannot be extracted safely from source code alone.

```md
You are enriching machine-readable Partner Components artifacts with curated design-system knowledge for AI agents.

## Objective
Improve the agent-facing artifacts by adding high-value annotations that help an LLM:

- choose the right component
- avoid misuse
- map common Figma patterns to Partner components
- understand composition guidance
- attach meaningful example descriptions and tags

## Read First
1. `docs/ai-artifacts.md`
2. `agent-artifacts/exports/component-catalog.generated.json`
3. `agent-artifacts/exports/component-catalog.annotations.json`
4. `agent-artifacts/exports/component-examples.generated.json`
5. `agent-artifacts/exports/component-examples.annotations.json`
6. `agent-artifacts/exports/design-tokens.json`
7. `agent-artifacts/source/figma-mapping-hints.json`
8. `agent-artifacts/source/figma-component-map.json`
9. `src/index.ts`
10. `src/components/**`
11. `src/components/**/*.stories.ts`
12. `tests/*.spec.ts`
13. `docs/styling-system.md`
14. `README.md`
15. The master Figma design-system file referenced in `docs/ai-artifacts.md`

## Files You May Update
1. `agent-artifacts/exports/component-catalog.annotations.json`
2. `agent-artifacts/exports/component-examples.annotations.json`
3. `agent-artifacts/source/figma-component-map.json`
4. `agent-artifacts/source/figma-mapping-hints.json`

## Files You Must Not Invent Facts In
1. `component-catalog.generated.json`
2. `component-examples.generated.json`
3. `design-tokens.json`

If a structural fact is missing there, propose improving the generator instead of fabricating the value.

## Allowed Enrichment Fields

### `component-catalog.annotations.json`

Per component, you may add:

- `purpose`
- `useWhen`
- `avoidWhen`
- `accessibilityNotes`
- `layoutConstraints`
- `compositionWith`
- `tags`

Do not add props, emits, slots, stories, or imports that are not already supported by source code.

### `component-examples.annotations.json`

Per example, you may add:

- `description`
- `tags`

Tags should be concise and reusable, such as:

- `form`
- `table`
- `navigation`
- `overlay`
- `feedback`
- `empty-state`
- `layout`
- `data-entry`
- `selection`
- `search`

### `figma-mapping-hints.json`

You may add curated mappings such as:

- Figma layer-name patterns
- preferred component mappings
- token usage hints
- ambiguity rules
- fallback rules

### `figma-component-map.json`

You may add or update:

- confirmed component-to-node mappings
- canonical frame references
- documentation-node references
- supporting token or brand pages that back component decisions

## Required Rules
1. Do not hallucinate non-existent components or props.
2. Base every annotation on repository evidence or clearly conservative design-system inference.
3. Prefer short, high-signal guidance over essay-style prose.
4. Keep `useWhen` and `avoidWhen` actionable.
5. Keep accessibility notes focused on user-visible and agent-relevant constraints.
6. For Figma mappings, prefer explicit patterns over vague recommendations.
7. When uncertain, leave the field out and note the gap rather than guessing.
8. If Figma MCP is available, prefer grounded mappings from the master design-system file over generic pattern assumptions.
9. Keep `figma-component-map.json` conservative: only record nodes that were directly confirmed in Figma.
10. If a generated `codeSnippet` is poor because the story lacks a canonical exportable example, note the gap and propose adding `parameters.exportableCode` to that story instead of inventing a permanent annotation-layer fix.

## Example Enrichment Style

Good `purpose`:
- "Primary action trigger for standard flows, including form submit and toolbar actions."

Good `useWhen`:
- "Use for the highest-priority action in a section or dialog."

Good `avoidWhen`:
- "Avoid for passive status display; use `PBadge` or `PTypography` instead."

Good Figma mapping:
- `"Primary Button" -> PButton variant=primary appearance=contained`
- `"Input + label + helper" -> compose PLabel + PTextInput + helper text wrapper in local layout`

## Acceptance Criteria
1. The annotations improve component selection without changing structural facts.
2. The Figma mappings are explicit enough for an agent to use directly.
3. The component-to-node registry captures confirmed canonical Figma references for future sync work.
4. Example descriptions and tags are helpful and not redundant.
5. The enriched outputs still validate after merge.

## Output Format
1. Apply edits directly to annotation files only.
2. Do not rewrite generated files by hand.
3. Run:
   - `npm run agent-artifacts:generate`
   - `npm run agent-artifacts:validate`
4. Provide a short summary:
   - Which components or examples gained meaningful annotations
   - Any unresolved ambiguity that still needs human design-system input
```
