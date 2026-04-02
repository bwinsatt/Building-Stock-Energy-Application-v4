import { cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, unlinkSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import { afterEach, describe, expect, test } from 'vitest'

const repoRoot = path.resolve(import.meta.dirname, '..')
const tempDirs: string[] = []

const requiredPublicArtifacts = [
  'agent-artifacts/exports/component-catalog.json',
  'agent-artifacts/exports/component-examples.json',
  'agent-artifacts/exports/design-tokens.json',
  'agent-artifacts/exports/figma-component-map.json',
  'agent-artifacts/exports/figma-mapping-hints.json',
  'agent-artifacts/exports/ai-artifacts.md',
]

afterEach(() => {
  while (tempDirs.length > 0) {
    const tempDir = tempDirs.pop()
    if (tempDir) {
      rmSync(tempDir, { recursive: true, force: true })
    }
  }
})

describe('agent artifact workflows', () => {
  test('generate creates deterministic artifacts, merges annotations, and preserves curated figma hints', async () => {
    const fixtureDir = createArtifactFixture()

    unlinkSync(path.join(fixtureDir, 'agent-artifacts/exports/component-catalog.annotations.json'))
    unlinkSync(path.join(fixtureDir, 'agent-artifacts/exports/component-examples.annotations.json'))

    const originalHints = readText(fixtureDir, 'agent-artifacts/source/figma-mapping-hints.json')
    const customHints = {
      schemaVersion: '1.0.0',
      generatedAt: '2026-01-01T00:00:00.000Z',
      mappings: [
        {
          pattern: 'Confirmation Dialog',
          component: 'PDialog',
        },
      ],
    }
    writeJson(fixtureDir, 'agent-artifacts/source/figma-mapping-hints.json', customHints)

    await runGenerate(fixtureDir)

    for (const artifactPath of [
      'agent-artifacts/exports/component-catalog.generated.json',
      'agent-artifacts/exports/component-catalog.json',
      'agent-artifacts/exports/component-examples.generated.json',
      'agent-artifacts/exports/component-examples.json',
      'agent-artifacts/exports/design-tokens.json',
      'agent-artifacts/exports/component-catalog.annotations.json',
      'agent-artifacts/exports/component-examples.annotations.json',
      'agent-artifacts/source/figma-mapping-hints.json',
    ]) {
      expect(existsSync(path.join(fixtureDir, artifactPath)), `${artifactPath} should exist`).toBe(true)
    }

    const componentCatalogGenerated = readJson(fixtureDir, 'agent-artifacts/exports/component-catalog.generated.json')
    expect(componentCatalogGenerated.schemaVersion).toBeTruthy()
    expect(componentCatalogGenerated.components.some((component: { name: string }) => component.name === 'PButton')).toBe(true)

    const componentCatalog = readJson(fixtureDir, 'agent-artifacts/exports/component-catalog.json')
    expect(componentCatalog.components.length).toBeGreaterThan(0)
    expect(componentCatalog.components.some((component: { name: string }) => component.name === 'PDialog')).toBe(true)

    const componentExamplesGenerated = readJson(fixtureDir, 'agent-artifacts/exports/component-examples.generated.json')
    const defaultButtonExample = componentExamplesGenerated.examples.find(
      (example: { componentName: string; storyName: string }) =>
        example.componentName === 'PButton' && example.storyName === 'Default',
    )
    expect(defaultButtonExample).toBeTruthy()
    expect(defaultButtonExample.codeSnippet).toContain('<PButton')
    expect(defaultButtonExample.codeSnippet).toContain('Click Me')
    expect(defaultButtonExample.codeSnippet).not.toContain('v-bind="args"')

    const designTokens = readJson(fixtureDir, 'agent-artifacts/exports/design-tokens.json')
    expect(designTokens.tokens.some((token: { cssVariable: string }) => token.cssVariable === '--accent')).toBe(true)

    expect(readText(fixtureDir, 'agent-artifacts/source/figma-mapping-hints.json')).not.toBe(originalHints)
    expect(readJson(fixtureDir, 'agent-artifacts/source/figma-mapping-hints.json')).toEqual(customHints)
  })

  test('generate merges curated annotations into the public outputs', async () => {
    const fixtureDir = createArtifactFixture()

    writeJson(fixtureDir, 'agent-artifacts/exports/component-catalog.annotations.json', {
      schemaVersion: '1.0.0',
      updatedAt: '2026-01-01T00:00:00.000Z',
      components: {
        PButton: {
          purpose: 'Curated button purpose',
          tags: ['actions'],
        },
      },
    })

    writeJson(fixtureDir, 'agent-artifacts/exports/component-examples.annotations.json', {
      schemaVersion: '1.0.0',
      updatedAt: '2026-01-01T00:00:00.000Z',
      examples: {
        'components-pbutton--default': {
          description: 'Curated default button example',
          tags: ['form'],
        },
      },
    })

    await runGenerate(fixtureDir)

    const componentCatalog = readJson(fixtureDir, 'agent-artifacts/exports/component-catalog.json')
    const buttonCatalogEntry = componentCatalog.components.find((component: { name: string }) => component.name === 'PButton')
    expect(buttonCatalogEntry.purpose).toBe('Curated button purpose')
    expect(buttonCatalogEntry.tags).toEqual(['actions'])

    const componentExamples = readJson(fixtureDir, 'agent-artifacts/exports/component-examples.json')
    const buttonExample = componentExamples.examples.find((example: { id: string }) => example.id === 'components-pbutton--default')
    expect(buttonExample.description).toBe('Curated default button example')
    expect(buttonExample.tags).toEqual(['form'])

    const generatedExamples = readJson(fixtureDir, 'agent-artifacts/exports/component-examples.generated.json')
    const generatedButtonExample = generatedExamples.examples.find((example: { id: string }) => example.id === 'components-pbutton--default')
    expect(generatedButtonExample.description).toBeUndefined()
    expect(generatedButtonExample.tags).toEqual([])
  })

  test('sync copies curated figma artifacts and contract docs into exports', async () => {
    const fixtureDir = createArtifactFixture()

    const figmaMap = {
      schemaVersion: '1.0.0',
      generatedAt: '2026-01-01T00:00:00.000Z',
      components: [
        {
          componentName: 'PDialog',
          repoStatus: 'implemented',
          status: 'matched',
          figmaNodes: [],
        },
      ],
    }
    const figmaHints = {
      schemaVersion: '1.0.0',
      generatedAt: '2026-01-01T00:00:00.000Z',
      mappings: [
        {
          pattern: 'Toast',
          component: 'PToast',
        },
      ],
    }

    writeJson(fixtureDir, 'agent-artifacts/source/figma-component-map.json', figmaMap)
    writeJson(fixtureDir, 'agent-artifacts/source/figma-mapping-hints.json', figmaHints)

    await runSync(fixtureDir)

    expect(readJson(fixtureDir, 'agent-artifacts/exports/figma-component-map.json')).toEqual(figmaMap)
    expect(readJson(fixtureDir, 'agent-artifacts/exports/figma-mapping-hints.json')).toEqual(figmaHints)

    const contractDoc = readText(fixtureDir, 'agent-artifacts/exports/ai-artifacts.md')
    expect(contractDoc).toContain('@partnerdevops/partner-components/agent-artifacts/exports/component-catalog.json')
  })

  test('sync fails clearly when a curated figma source file is missing', async () => {
    const fixtureDir = createArtifactFixture()
    unlinkSync(path.join(fixtureDir, 'agent-artifacts/source/figma-component-map.json'))

    await expect(runSync(fixtureDir)).rejects.toThrow('Missing curated Figma artifact source')
  })

  test('prepare workflow validates the synced export set', async () => {
    const fixtureDir = createArtifactFixture()

    await runGenerate(fixtureDir)
    await runSync(fixtureDir)
    await runValidate(fixtureDir)

    for (const artifactPath of requiredPublicArtifacts) {
      expect(existsSync(path.join(fixtureDir, artifactPath)), `${artifactPath} should exist`).toBe(true)
    }
  })

  test('package manifest exposes only the published artifact contract files', () => {
    const packageJson = readJson(repoRoot, 'package.json')
    const packagedFiles = new Set(packageJson.files)

    expect(packageJson.exports['./agent-artifacts/exports/component-catalog.json']).toBe('./agent-artifacts/exports/component-catalog.json')
    expect(packageJson.exports['./agent-artifacts/exports/component-examples.json']).toBe('./agent-artifacts/exports/component-examples.json')
    expect(packageJson.exports['./agent-artifacts/exports/design-tokens.json']).toBe('./agent-artifacts/exports/design-tokens.json')
    expect(packageJson.exports['./agent-artifacts/exports/figma-component-map.json']).toBe('./agent-artifacts/exports/figma-component-map.json')
    expect(packageJson.exports['./agent-artifacts/exports/figma-mapping-hints.json']).toBe('./agent-artifacts/exports/figma-mapping-hints.json')
    expect(packageJson.exports['./agent-artifacts/exports/ai-artifacts.md']).toBe('./agent-artifacts/exports/ai-artifacts.md')
    expect(packageJson.exports['./agent-artifacts/exports/*']).toBeUndefined()
    expect(packageJson.exports['./agent-artifacts/schemas/*']).toBeUndefined()

    expect(packagedFiles.has('agent-artifacts/exports/component-catalog.json')).toBe(true)
    expect(packagedFiles.has('agent-artifacts/exports/component-examples.json')).toBe(true)
    expect(packagedFiles.has('agent-artifacts/exports/design-tokens.json')).toBe(true)
    expect(packagedFiles.has('agent-artifacts/exports/figma-component-map.json')).toBe(true)
    expect(packagedFiles.has('agent-artifacts/exports/figma-mapping-hints.json')).toBe(true)
    expect(packagedFiles.has('agent-artifacts/exports/ai-artifacts.md')).toBe(true)
    expect(packagedFiles.has('agent-artifacts/source')).toBe(false)

    expect(packageJson.scripts.build).toContain('agent-artifacts:prepare')
    expect(packageJson.scripts.prepack).toContain('agent-artifacts:generate')
    expect(packageJson.scripts.prepack).toContain('npm run build')
  })

  test('generate extracts script metadata from Vue SFCs when setup is not the first script attribute', async () => {
    const fixtureDir = createArtifactFixture()
    const componentDir = path.join(fixtureDir, 'src/components/PFixtureScriptOrder')

    mkdirSync(componentDir, { recursive: true })

    writeFileSync(
      path.join(componentDir, 'PFixtureScriptOrder.vue'),
      `<script lang="ts" setup>
interface PFixtureScriptOrderProps {
  label?: string
}

withDefaults(defineProps<PFixtureScriptOrderProps>(), {
  label: 'fixture',
})
</script>

<template>
  <div>{{ label }}</div>
</template>
`,
    )
    writeFileSync(
      path.join(componentDir, 'index.ts'),
      'export { default as PFixtureScriptOrder } from "./PFixtureScriptOrder.vue"\n',
    )
    writeFileSync(
      path.join(fixtureDir, 'src/index.ts'),
      `${readText(repoRoot, 'src/index.ts')}export { PFixtureScriptOrder } from './components/PFixtureScriptOrder'\n`,
    )

    await runGenerate(fixtureDir)

    const componentCatalogGenerated = readJson(fixtureDir, 'agent-artifacts/exports/component-catalog.generated.json')
    const fixtureEntry = componentCatalogGenerated.components.find(
      (component: { name: string }) => component.name === 'PFixtureScriptOrder',
    )

    expect(fixtureEntry).toBeTruthy()
    expect(fixtureEntry.props).toEqual([
      expect.objectContaining({
        name: 'label',
        type: 'string',
        required: false,
      }),
    ])
  })
})

function createArtifactFixture() {
  const fixtureDir = mkdtempSync(path.join(tmpdir(), 'partner-components-agent-artifacts-'))
  tempDirs.push(fixtureDir)

  copyFromRepo('src', fixtureDir)
  copyFromRepo('tests', fixtureDir)
  copyFromRepo('docs/ai-artifacts.md', fixtureDir)
  copyFromRepo('agent-artifacts/schemas', fixtureDir)
  copyFromRepo('agent-artifacts/exports/component-catalog.annotations.json', fixtureDir)
  copyFromRepo('agent-artifacts/exports/component-examples.annotations.json', fixtureDir)
  copyFromRepo('agent-artifacts/source/figma-component-map.json', fixtureDir)
  copyFromRepo('agent-artifacts/source/figma-mapping-hints.json', fixtureDir)

  return fixtureDir
}

function copyFromRepo(relativePath: string, targetRoot: string) {
  const sourcePath = path.join(repoRoot, relativePath)
  const targetPath = path.join(targetRoot, relativePath)
  mkdirSync(path.dirname(targetPath), { recursive: true })
  cpSync(sourcePath, targetPath, { recursive: true })
}

async function runGenerate(cwd: string) {
  await runModuleMain(cwd, 'scripts/generate-agent-artifacts.mjs')
}

async function runSync(cwd: string) {
  await runModuleMain(cwd, 'scripts/sync-agent-artifacts.mjs')
}

async function runModuleMain(cwd: string, scriptPath: string) {
  const previousCwd = process.cwd()

  try {
    process.chdir(cwd)
    const scriptUrl = pathToFileURL(path.join(repoRoot, scriptPath)).href
    const module = await import(`${scriptUrl}?cwd=${encodeURIComponent(cwd)}&t=${Date.now()}-${Math.random()}`)
    module.main()
  } finally {
    process.chdir(previousCwd)
  }
}

function runValidate(cwd: string) {
  return runModuleMain(cwd, 'scripts/validate-agent-artifacts.mjs')
}

function readJson(cwd: string, filePath: string) {
  return JSON.parse(readText(cwd, filePath))
}

function readText(cwd: string, filePath: string) {
  return readFileSync(path.join(cwd, filePath), 'utf8')
}

function writeJson(cwd: string, filePath: string, value: unknown) {
  const fullPath = path.join(cwd, filePath)
  mkdirSync(path.dirname(fullPath), { recursive: true })
  writeFileSync(fullPath, `${JSON.stringify(value, null, 2)}\n`)
}
