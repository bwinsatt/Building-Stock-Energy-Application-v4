import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import Ajv2020 from 'ajv/dist/2020.js'
import addFormats from 'ajv-formats'

function main() {
  const repoRoot = process.cwd()
  const requiredArtifactFiles = [
    'agent-artifacts/exports/component-catalog.json',
    'agent-artifacts/exports/component-examples.json',
    'agent-artifacts/exports/design-tokens.json',
    'agent-artifacts/exports/figma-component-map.json',
    'agent-artifacts/exports/figma-mapping-hints.json',
    'agent-artifacts/exports/ai-artifacts.md',
  ]

  const schemaPairs = [
    ['agent-artifacts/schemas/component-catalog.schema.json', 'agent-artifacts/exports/component-catalog.generated.json'],
    ['agent-artifacts/schemas/component-catalog.schema.json', 'agent-artifacts/exports/component-catalog.json'],
    ['agent-artifacts/schemas/component-examples.schema.json', 'agent-artifacts/exports/component-examples.generated.json'],
    ['agent-artifacts/schemas/component-examples.schema.json', 'agent-artifacts/exports/component-examples.json'],
    ['agent-artifacts/schemas/design-tokens.schema.json', 'agent-artifacts/exports/design-tokens.json'],
    ['agent-artifacts/schemas/figma-component-map.schema.json', 'agent-artifacts/exports/figma-component-map.json'],
    ['agent-artifacts/schemas/figma-mapping-hints.schema.json', 'agent-artifacts/exports/figma-mapping-hints.json'],
  ]

  const ajv = new Ajv2020({
    allErrors: true,
    strict: false,
  })
  addFormats(ajv)

  const validatorCache = new Map()
  let hasErrors = false

  for (const filePath of requiredArtifactFiles) {
    const fullPath = path.join(repoRoot, filePath)

    if (!fs.existsSync(fullPath)) {
      hasErrors = true
      console.error(`Missing required artifact: ${filePath}`)
      continue
    }

    console.log(`ok ${filePath}`)
  }

  for (const [schemaPath, dataPath] of schemaPairs) {
    const fullSchemaPath = path.join(repoRoot, schemaPath)
    const fullDataPath = path.join(repoRoot, dataPath)
    const data = JSON.parse(fs.readFileSync(fullDataPath, 'utf8'))
    const validate = getValidator(fullSchemaPath)

    if (!validate(data)) {
      hasErrors = true
      console.error(`Schema validation failed for ${dataPath}`)
      console.error(JSON.stringify(validate.errors, null, 2))
      continue
    }

    console.log(`ok ${dataPath}`)
  }

  if (hasErrors) {
    process.exitCode = 1
  }

  function getValidator(fullSchemaPath) {
    const cachedValidator = validatorCache.get(fullSchemaPath)
    if (cachedValidator) {
      return cachedValidator
    }

    const schema = JSON.parse(fs.readFileSync(fullSchemaPath, 'utf8'))
    const validator = ajv.compile(schema)
    validatorCache.set(fullSchemaPath, validator)
    return validator
  }
}

export { main }

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main()
}
