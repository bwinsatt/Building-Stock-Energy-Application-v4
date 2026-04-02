import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import * as ts from 'typescript'

const repoRoot = process.cwd()
const packageName = '@partnerdevops/partner-components'
const schemaVersion = '1.0.0'
const exportsDir = path.join(repoRoot, 'agent-artifacts', 'exports')
const sourceDir = path.join(repoRoot, 'agent-artifacts', 'source')
const unresolved = Symbol('unresolved')

function main() {
  fs.mkdirSync(exportsDir, { recursive: true })
  fs.mkdirSync(sourceDir, { recursive: true })

  const generatedAt = new Date().toISOString()
  const componentExports = extractPublicComponentExports()
  const storyData = extractStories(componentExports)
  const designTokens = extractDesignTokens(generatedAt)

  const componentCatalogGenerated = {
    schemaVersion,
    generatedAt,
    components: componentExports
      .map((componentExport) => buildGeneratedComponent(componentExport, storyData.byComponent.get(componentExport.name) ?? []))
      .sort((left, right) => left.name.localeCompare(right.name)),
  }

  const componentAnnotations = ensureAnnotationsFile(
    path.join(exportsDir, 'component-catalog.annotations.json'),
    { schemaVersion, updatedAt: generatedAt, components: {} },
  )
  const componentCatalog = {
    schemaVersion,
    generatedAt,
    components: componentCatalogGenerated.components.map((component) =>
      mergeRecords(component, componentAnnotations.components?.[component.name] ?? componentAnnotations.components?.[component.id]),
    ),
  }

  const componentExamplesGenerated = {
    schemaVersion,
    generatedAt,
    examples: storyData.examples.sort((left, right) => left.id.localeCompare(right.id)),
  }
  const exampleAnnotations = ensureAnnotationsFile(
    path.join(exportsDir, 'component-examples.annotations.json'),
    { schemaVersion, updatedAt: generatedAt, examples: {} },
  )
  const componentExamples = {
    schemaVersion,
    generatedAt,
    examples: componentExamplesGenerated.examples.map((example) =>
      mergeRecords(example, exampleAnnotations.examples?.[example.id]),
    ),
  }

  const figmaMappingHintsPath = path.join(sourceDir, 'figma-mapping-hints.json')
  ensureSchemaFile(figmaMappingHintsPath, {
    schemaVersion,
    generatedAt,
    mappings: [],
  })

  writeJson(path.join(exportsDir, 'component-catalog.generated.json'), componentCatalogGenerated)
  writeJson(path.join(exportsDir, 'component-catalog.json'), componentCatalog)
  writeJson(path.join(exportsDir, 'component-examples.generated.json'), componentExamplesGenerated)
  writeJson(path.join(exportsDir, 'component-examples.json'), componentExamples)
  writeJson(path.join(exportsDir, 'design-tokens.json'), designTokens)

  console.log(`Generated agent artifacts in ${toRepoPath(exportsDir)}`)
}

function extractPublicComponentExports() {
  const indexPath = path.join(repoRoot, 'src', 'index.ts')
  const sourceFile = createTsSourceFile(indexPath, fs.readFileSync(indexPath, 'utf8'))
  const exports = []

  for (const statement of sourceFile.statements) {
    if (!ts.isExportDeclaration(statement) || statement.isTypeOnly || !statement.moduleSpecifier || !statement.exportClause) {
      continue
    }

    if (!ts.isNamedExports(statement.exportClause)) {
      continue
    }

    const moduleSpecifier = statement.moduleSpecifier.text
    const exportModulePath = resolveLocalModule(indexPath, moduleSpecifier)

    for (const element of statement.exportClause.elements) {
      const name = element.name.text
      if (!isPublicComponentName(name)) {
        continue
      }

      const sourcePath = exportModulePath ? resolveComponentSourceFile(exportModulePath, name) ?? exportModulePath : null
      exports.push({
        name,
        id: toComponentId(name),
        exportModulePath,
        sourcePath,
      })
    }
  }

  return exports
}

function buildGeneratedComponent(componentExport, stories) {
  const filesToInspect = compactUnique([componentExport.sourcePath, componentExport.exportModulePath])
  const propMap = new Map()
  const emitMap = new Map()
  const defaultValues = new Map()
  const slotNames = new Set()

  for (const filePath of filesToInspect) {
    const parsedComponentFile = parseComponentFile(filePath)
    const props = extractPropsFromParsedFile(parsedComponentFile, componentExport.name)
    for (const prop of props) {
      propMap.set(prop.name, mergePropRecords(propMap.get(prop.name), prop))
    }

    const emits = extractEmitsFromParsedFile(parsedComponentFile, componentExport.name)
    for (const emit of emits) {
      emitMap.set(emit.name, mergeRecords(emitMap.get(emit.name), emit))
    }

    for (const [name, value] of extractDefaultValuesFromParsedFile(parsedComponentFile)) {
      defaultValues.set(name, value)
    }

    for (const slotName of extractSlotsFromParsedFile(parsedComponentFile)) {
      slotNames.add(slotName)
    }
  }

  const variants = mergeVariants(stories.flatMap((story) => story.variants))
  for (const variant of variants) {
    const existingProp = propMap.get(variant.name)
    if (existingProp) {
      propMap.set(variant.name, mergePropRecords(existingProp, { options: variant.values }))
    }
  }

  const props = Array.from(propMap.values())
    .map((prop) => {
      if (defaultValues.has(prop.name)) {
        return { ...prop, default: defaultValues.get(prop.name) }
      }

      return prop
    })
    .sort((left, right) => left.name.localeCompare(right.name))

  return {
    id: componentExport.id,
    name: componentExport.name,
    import: {
      package: packageName,
      named: componentExport.name,
    },
    status: 'stable',
    source: {
      file: toRepoPath(componentExport.sourcePath ?? componentExport.exportModulePath),
    },
    props,
    slots: Array.from(slotNames)
      .sort((left, right) => left.localeCompare(right))
      .map((slotName) => ({ name: slotName })),
    emits: Array.from(emitMap.values()).sort((left, right) => left.name.localeCompare(right.name)),
    variants,
    layoutConstraints: [],
    accessibilityNotes: [],
    useWhen: [],
    avoidWhen: [],
    compositionWith: [],
    stories: stories.map((story) => ({
      id: story.storyId,
      name: story.storyName,
      file: story.sourceFile,
    })),
    tests: listMatchingTests(componentExport.name).map((file) => ({ file })),
    tags: [],
  }
}

function extractStories(componentExports) {
  const publicComponentNames = new Set(componentExports.map((componentExport) => componentExport.name))
  const storyFiles = listFiles(path.join(repoRoot, 'src', 'components'), (filePath) => filePath.endsWith('.stories.ts'))
  const examples = []
  const byComponent = new Map()

  for (const storyFile of storyFiles) {
    const storyContext = parseModuleContext(storyFile)
    const metaObject = resolveDefaultExportObject(storyContext)
    const title = getStringPropertyValue(metaObject, 'title')
    const componentName = title?.split('/').pop()

    if (!componentName || !publicComponentNames.has(componentName)) {
      continue
    }

    const storyVariants = extractArgTypeVariants(storyContext, metaObject)

    for (const statement of storyContext.sourceFile.statements) {
      if (!ts.isVariableStatement(statement) || !hasModifier(statement.modifiers, ts.SyntaxKind.ExportKeyword)) {
        continue
      }

      for (const declaration of statement.declarationList.declarations) {
        if (!ts.isIdentifier(declaration.name) || !declaration.initializer) {
          continue
        }

        const storyObject = getObjectLiteral(declaration.initializer, storyContext)
        if (!storyObject) {
          continue
        }

        const storyName = declaration.name.text
        const storyId = `${slugify(title)}--${slugify(storyName)}`
        const storyArgs = getEvaluatedObjectProperty(storyObject, 'args', storyContext)
        const storySpecificVariants = extractArgTypeVariants(storyContext, storyObject)
        const exportableCode = extractStoryExportableCode(storyContext, storyObject)
        const template = extractStoryTemplate(storyContext, storyObject)

        const example = {
          id: storyId,
          storyId,
          storyName,
          componentName,
          sourceFile: toRepoPath(storyFile),
          args: storyArgs && storyArgs !== unresolved ? storyArgs : {},
          ...((exportableCode ?? template) ? { codeSnippet: exportableCode ?? template } : {}),
          tags: [],
        }

        examples.push(example)

        const storyReference = {
          storyId,
          storyName,
          sourceFile: toRepoPath(storyFile),
          variants: mergeVariants([...storyVariants, ...storySpecificVariants]),
        }

        const existingStories = byComponent.get(componentName) ?? []
        existingStories.push(storyReference)
        byComponent.set(componentName, existingStories)
      }
    }
  }

  for (const [componentName, componentStories] of byComponent.entries()) {
    byComponent.set(
      componentName,
      componentStories.sort((left, right) => left.storyName.localeCompare(right.storyName)),
    )
  }

  return { examples, byComponent }
}

function extractDesignTokens(generatedAt) {
  const styleFiles = listFiles(path.join(repoRoot, 'src', 'styles'), (filePath) => filePath.endsWith('.css'))
  const tokens = []

  for (const filePath of styleFiles) {
    const content = fs.readFileSync(filePath, 'utf8')
    const matches = content.matchAll(/(--[A-Za-z0-9-_]+)\s*:\s*([^;]+);/g)

    for (const match of matches) {
      const cssVariable = match[1]
      const value = match[2].trim()
      tokens.push({
        name: cssVariable.replace(/^--/, ''),
        category: inferTokenCategory(filePath, cssVariable),
        value,
        cssVariable,
        sourceFile: toRepoPath(filePath),
      })
    }
  }

  tokens.sort((left, right) =>
    left.name.localeCompare(right.name) || left.sourceFile.localeCompare(right.sourceFile),
  )

  return {
    schemaVersion,
    generatedAt,
    tokens,
  }
}

function parseComponentFile(filePath) {
  const extension = path.extname(filePath)
  if (extension === '.vue') {
    const content = fs.readFileSync(filePath, 'utf8')
    const scriptContent = extractVueScriptContent(content)
    const templateContent = extractVueTemplateContent(content)

    return {
      filePath,
      sourceFile: scriptContent ? createTsSourceFile(`${filePath}.ts`, scriptContent) : null,
      sourceText: scriptContent,
      templateContent,
    }
  }

  const sourceText = fs.readFileSync(filePath, 'utf8')
  return {
    filePath,
    sourceFile: createTsSourceFile(filePath, sourceText),
    sourceText,
    templateContent: '',
  }
}

function extractPropsFromParsedFile(parsedFile, componentName) {
  if (!parsedFile.sourceFile) {
    return []
  }

  const interfaceNames = [`${componentName}Props`, 'Props']
  const props = []

  for (const interfaceName of interfaceNames) {
    const interfaceDeclaration = findInterfaceDeclaration(parsedFile.sourceFile, interfaceName)
    if (!interfaceDeclaration) {
      continue
    }

    for (const member of interfaceDeclaration.members) {
      if (!ts.isPropertySignature(member)) {
        continue
      }

      const name = getPropertyName(member.name)
      if (!name) {
        continue
      }

      const prop = {
        name,
        ...(member.type ? { type: member.type.getText(parsedFile.sourceFile) } : {}),
        ...(member.questionToken ? { required: false } : { required: true }),
      }

      props.push(prop)
    }

    if (props.length > 0) {
      return props
    }
  }

  return []
}

function extractEmitsFromParsedFile(parsedFile, componentName) {
  if (!parsedFile.sourceFile) {
    return []
  }

  const interfaceNames = [`${componentName}Emits`, 'Emits']
  const emits = []

  for (const interfaceName of interfaceNames) {
    const interfaceDeclaration = findInterfaceDeclaration(parsedFile.sourceFile, interfaceName)
    if (!interfaceDeclaration) {
      continue
    }

    for (const member of interfaceDeclaration.members) {
      if (ts.isCallSignatureDeclaration(member)) {
        const eventNameNode = member.parameters[0]?.type
        const payloadNode = member.parameters[1]?.type
        const eventName = eventNameNode && ts.isLiteralTypeNode(eventNameNode) && ts.isStringLiteral(eventNameNode.literal)
          ? eventNameNode.literal.text
          : null

        if (eventName) {
          emits.push({
            name: eventName,
            ...(payloadNode ? { payload: payloadNode.getText(parsedFile.sourceFile) } : {}),
          })
        }
      }

      if (ts.isPropertySignature(member)) {
        const eventName = getPropertyName(member.name)
        if (!eventName) {
          continue
        }

        emits.push({
          name: eventName,
          ...(member.type ? { payload: member.type.getText(parsedFile.sourceFile) } : {}),
        })
      }
    }

    if (emits.length > 0) {
      return emits
    }
  }

  return []
}

function extractDefaultValuesFromParsedFile(parsedFile) {
  if (!parsedFile.sourceFile) {
    return new Map()
  }

  const defaultValues = new Map()

  for (const statement of parsedFile.sourceFile.statements) {
    if (!ts.isVariableStatement(statement)) {
      continue
    }

    for (const declaration of statement.declarationList.declarations) {
      if (!declaration.initializer || !ts.isCallExpression(declaration.initializer)) {
        continue
      }

      const callExpression = declaration.initializer
      if (!ts.isIdentifier(callExpression.expression) || callExpression.expression.text !== 'withDefaults') {
        continue
      }

      const defaultsNode = callExpression.arguments[1]
      if (!defaultsNode || !ts.isObjectLiteralExpression(defaultsNode)) {
        continue
      }

      for (const property of defaultsNode.properties) {
        if (!ts.isPropertyAssignment(property)) {
          continue
        }

        const name = getPropertyName(property.name)
        if (!name) {
          continue
        }

        const value = evaluateNode(property.initializer, parsedFile.filePath)
        if (value !== unresolved) {
          defaultValues.set(name, value)
        }
      }
    }
  }

  return defaultValues
}

function extractSlotsFromParsedFile(parsedFile) {
  if (!parsedFile.templateContent) {
    return []
  }

  const slotNames = new Set()
  const slotPattern = /<slot(?:\s+[^>]*?name=["']([^"']+)["'])?[^>]*>/g

  for (const match of parsedFile.templateContent.matchAll(slotPattern)) {
    slotNames.add(match[1] ?? 'default')
  }

  return Array.from(slotNames)
}

function extractArgTypeVariants(moduleContext, objectLiteral) {
  const argTypesObject = getObjectProperty(objectLiteral, 'argTypes')
  if (!argTypesObject || !ts.isObjectLiteralExpression(argTypesObject.initializer)) {
    return []
  }

  const variants = []

  for (const property of argTypesObject.initializer.properties) {
    if (!ts.isPropertyAssignment(property)) {
      continue
    }

    const variantName = getPropertyName(property.name)
    const variantConfig = getObjectLiteral(property.initializer, moduleContext)
    if (!variantName || !variantConfig) {
      continue
    }

    const options = getEvaluatedObjectProperty(variantConfig, 'options', moduleContext)
    if (!Array.isArray(options) || options.length === 0) {
      continue
    }

    const values = options
      .filter((option) => ['string', 'number', 'boolean'].includes(typeof option))
      .map((option) => String(option))

    if (values.length === 0) {
      continue
    }

    variants.push({ name: variantName, values })
  }

  return variants
}

function extractStoryTemplate(moduleContext, storyObject) {
  const renderProperty = getObjectProperty(storyObject, 'render')
  if (!renderProperty) {
    return null
  }

  return extractTemplateFromExpression(renderProperty.initializer, moduleContext)
}

function extractStoryExportableCode(moduleContext, storyObject) {
  const parameters = getNestedObjectLiteral(storyObject, ['parameters'], moduleContext)
  if (!parameters) {
    return null
  }

  const exportableCode = getEvaluatedObjectProperty(parameters, 'exportableCode', moduleContext)
  return typeof exportableCode === 'string' ? exportableCode.trim() : null
}

function extractTemplateFromExpression(expression, moduleContext) {
  const node = unwrapExpression(expression)

  if (ts.isIdentifier(node)) {
    const localValue = resolveValueNode(moduleContext.filePath, node.text)
    return localValue ? extractTemplateFromExpression(localValue.node, parseModuleContext(localValue.filePath)) : null
  }

  if (ts.isCallExpression(node)) {
    return extractTemplateFromExpression(node.expression, moduleContext)
  }

  if (ts.isArrowFunction(node) || ts.isFunctionExpression(node) || ts.isFunctionDeclaration(node)) {
    if (ts.isObjectLiteralExpression(node.body)) {
      return getTemplateFromObjectLiteral(node.body, moduleContext)
    }

    if (ts.isParenthesizedExpression(node.body) || ts.isArrowFunction(node.body) || ts.isObjectLiteralExpression(node.body)) {
      return extractTemplateFromExpression(node.body, moduleContext)
    }

    if (ts.isBlock(node.body)) {
      for (const statement of node.body.statements) {
        if (ts.isReturnStatement(statement) && statement.expression) {
          return extractTemplateFromExpression(statement.expression, moduleContext)
        }
      }
    }
  }

  if (ts.isObjectLiteralExpression(node)) {
    return getTemplateFromObjectLiteral(node, moduleContext)
  }

  return null
}

function getTemplateFromObjectLiteral(objectLiteral, moduleContext) {
  const templateValue = getEvaluatedObjectProperty(objectLiteral, 'template', moduleContext)
  return typeof templateValue === 'string' ? templateValue.trim() : null
}

function listMatchingTests(componentName) {
  const testsDir = path.join(repoRoot, 'tests')
  if (!fs.existsSync(testsDir)) {
    return []
  }

  return listFiles(testsDir, (filePath) => filePath.endsWith('.spec.ts'))
    .filter((filePath) => path.basename(filePath, '.spec.ts') === componentName)
    .map((filePath) => toRepoPath(filePath))
    .sort((left, right) => left.localeCompare(right))
}

function resolveComponentSourceFile(exportModulePath, componentName) {
  if (exportModulePath.endsWith('.vue')) {
    return exportModulePath
  }

  const moduleContext = parseModuleContext(exportModulePath)
  const exportEntry = moduleContext.exports.get(componentName)
  if (!exportEntry) {
    return exportModulePath
  }

  if (exportEntry.kind === 'local') {
    const initializerNode = moduleContext.values.get(exportEntry.localName)
    if (initializerNode && ts.isCallExpression(initializerNode)) {
      return exportModulePath
    }

    return exportModulePath
  }

  if (exportEntry.kind === 'reexport') {
    return exportEntry.sourcePath.endsWith('.vue')
      ? exportEntry.sourcePath
      : resolveComponentSourceFile(exportEntry.sourcePath, exportEntry.importedName)
  }

  return exportModulePath
}

function parseModuleContext(filePath) {
  if (moduleContextCache.has(filePath)) {
    return moduleContextCache.get(filePath)
  }

  const sourceText = fs.readFileSync(filePath, 'utf8')
  const sourceFile = createTsSourceFile(filePath, sourceText)
  const context = {
    filePath,
    sourceFile,
    sourceText,
    values: new Map(),
    functions: new Map(),
    imports: new Map(),
    exports: new Map(),
  }

  for (const statement of sourceFile.statements) {
    if (ts.isImportDeclaration(statement) && ts.isStringLiteral(statement.moduleSpecifier) && statement.importClause) {
      const sourcePath = resolveLocalModule(filePath, statement.moduleSpecifier.text)
      if (!sourcePath) {
        continue
      }

      const importClause = statement.importClause
      if (importClause.name) {
        context.imports.set(importClause.name.text, {
          sourcePath,
          importedName: 'default',
        })
      }

      const namedBindings = importClause.namedBindings
      if (namedBindings && ts.isNamedImports(namedBindings)) {
        for (const element of namedBindings.elements) {
          context.imports.set(element.name.text, {
            sourcePath,
            importedName: element.propertyName?.text ?? element.name.text,
          })
        }
      }
    }

    if (ts.isVariableStatement(statement)) {
      for (const declaration of statement.declarationList.declarations) {
        if (!ts.isIdentifier(declaration.name) || !declaration.initializer) {
          continue
        }

        context.values.set(declaration.name.text, declaration.initializer)
        if (isFunctionLikeInitializer(declaration.initializer)) {
          context.functions.set(declaration.name.text, declaration.initializer)
        }

        if (hasModifier(statement.modifiers, ts.SyntaxKind.ExportKeyword)) {
          context.exports.set(declaration.name.text, {
            kind: 'local',
            localName: declaration.name.text,
          })
        }
      }
    }

    if (ts.isFunctionDeclaration(statement) && statement.name) {
      context.functions.set(statement.name.text, statement)
      if (hasModifier(statement.modifiers, ts.SyntaxKind.ExportKeyword)) {
        context.exports.set(statement.name.text, {
          kind: 'function',
          localName: statement.name.text,
        })
      }
    }

    if (ts.isExportDeclaration(statement) && statement.moduleSpecifier && statement.exportClause && ts.isNamedExports(statement.exportClause)) {
      const sourcePath = resolveLocalModule(filePath, statement.moduleSpecifier.text)
      if (!sourcePath) {
        continue
      }

      for (const element of statement.exportClause.elements) {
        context.exports.set(element.name.text, {
          kind: 'reexport',
          sourcePath,
          importedName: element.propertyName?.text ?? element.name.text,
        })
      }
    }
  }

  moduleContextCache.set(filePath, context)
  return context
}

function resolveDefaultExportObject(moduleContext) {
  for (const statement of moduleContext.sourceFile.statements) {
    if (!ts.isExportAssignment(statement)) {
      continue
    }

    return getObjectLiteral(statement.expression, moduleContext)
  }

  return null
}

function getObjectLiteral(node, moduleContext) {
  const expression = unwrapExpression(node)

  if (ts.isObjectLiteralExpression(expression)) {
    return expression
  }

  if (ts.isIdentifier(expression)) {
    const resolved = resolveValueNode(moduleContext.filePath, expression.text)
    if (resolved) {
      return getObjectLiteral(resolved.node, parseModuleContext(resolved.filePath))
    }
  }

  return null
}

function getObjectProperty(objectLiteral, propertyName) {
  for (const property of objectLiteral.properties) {
    if (!ts.isPropertyAssignment(property)) {
      continue
    }

    if (getPropertyName(property.name) === propertyName) {
      return property
    }
  }

  return null
}

function getStringPropertyValue(objectLiteral, propertyName) {
  const property = getObjectProperty(objectLiteral, propertyName)
  if (!property) {
    return null
  }

  const value = property.initializer
  if (ts.isStringLiteral(value) || ts.isNoSubstitutionTemplateLiteral(value)) {
    return value.text
  }

  return null
}

function getEvaluatedObjectProperty(objectLiteral, propertyName, moduleContext) {
  const property = getObjectProperty(objectLiteral, propertyName)
  if (!property) {
    return unresolved
  }

  return evaluateNode(property.initializer, moduleContext.filePath)
}

function getNestedObjectLiteral(objectLiteral, propertyPath, moduleContext) {
  let current = objectLiteral

  for (const propertyName of propertyPath) {
    const property = getObjectProperty(current, propertyName)
    if (!property) {
      return null
    }

    current = getObjectLiteral(property.initializer, moduleContext)
    if (!current) {
      return null
    }
  }

  return current
}

function evaluateNode(node, filePath, seen = new Set()) {
  const expression = unwrapExpression(node)

  if (ts.isStringLiteral(expression) || ts.isNoSubstitutionTemplateLiteral(expression)) {
    return expression.text
  }

  if (ts.isNumericLiteral(expression)) {
    return Number(expression.text)
  }

  if (expression.kind === ts.SyntaxKind.TrueKeyword) {
    return true
  }

  if (expression.kind === ts.SyntaxKind.FalseKeyword) {
    return false
  }

  if (expression.kind === ts.SyntaxKind.NullKeyword) {
    return null
  }

  if (ts.isIdentifier(expression)) {
    if (expression.text === 'undefined') {
      return undefined
    }

    const visitKey = `${filePath}:${expression.text}`
    if (seen.has(visitKey)) {
      return unresolved
    }

    seen.add(visitKey)
    const resolved = resolveValueNode(filePath, expression.text)
    if (!resolved) {
      return unresolved
    }

    return evaluateNode(resolved.node, resolved.filePath, seen)
  }

  if (ts.isArrayLiteralExpression(expression)) {
    const result = []
    for (const element of expression.elements) {
      if (ts.isSpreadElement(element)) {
        const spreadValue = evaluateNode(element.expression, filePath, seen)
        if (Array.isArray(spreadValue)) {
          result.push(...spreadValue)
        }
        continue
      }

      const value = evaluateNode(element, filePath, seen)
      if (value !== unresolved) {
        result.push(value)
      }
    }
    return result
  }

  if (ts.isObjectLiteralExpression(expression)) {
    const result = {}
    for (const property of expression.properties) {
      if (ts.isPropertyAssignment(property)) {
        const key = getPropertyName(property.name)
        if (!key) {
          continue
        }

        const value = evaluateNode(property.initializer, filePath, seen)
        if (value !== unresolved) {
          result[key] = value
        }
      }

      if (ts.isShorthandPropertyAssignment(property)) {
        const value = evaluateNode(property.name, filePath, seen)
        if (value !== unresolved) {
          result[property.name.text] = value
        }
      }

      if (ts.isSpreadAssignment(property)) {
        const value = evaluateNode(property.expression, filePath, seen)
        if (value && typeof value === 'object' && !Array.isArray(value)) {
          Object.assign(result, value)
        }
      }
    }
    return result
  }

  if (ts.isPrefixUnaryExpression(expression) && ts.isNumericLiteral(expression.operand)) {
    if (expression.operator === ts.SyntaxKind.MinusToken) {
      return -Number(expression.operand.text)
    }

    if (expression.operator === ts.SyntaxKind.PlusToken) {
      return Number(expression.operand.text)
    }
  }

  return unresolved
}

function resolveValueNode(filePath, name) {
  const moduleContext = parseModuleContext(filePath)
  const localValue = moduleContext.values.get(name) ?? moduleContext.functions.get(name)
  if (localValue) {
    return { filePath, node: localValue }
  }

  const importedValue = moduleContext.imports.get(name)
  if (!importedValue) {
    return null
  }

  if (importedValue.importedName === 'default') {
    return null
  }

  const importedContext = parseModuleContext(importedValue.sourcePath)
  const exportEntry = importedContext.exports.get(importedValue.importedName)
  if (!exportEntry) {
    const directValue = importedContext.values.get(importedValue.importedName) ?? importedContext.functions.get(importedValue.importedName)
    return directValue ? { filePath: importedValue.sourcePath, node: directValue } : null
  }

  if (exportEntry.kind === 'local' || exportEntry.kind === 'function') {
    const exportedNode = importedContext.values.get(exportEntry.localName) ?? importedContext.functions.get(exportEntry.localName)
    return exportedNode ? { filePath: importedValue.sourcePath, node: exportedNode } : null
  }

  if (exportEntry.kind === 'reexport') {
    return resolveValueNode(exportEntry.sourcePath, exportEntry.importedName)
  }

  return null
}

function findInterfaceDeclaration(sourceFile, interfaceName) {
  for (const statement of sourceFile.statements) {
    if (ts.isInterfaceDeclaration(statement) && statement.name.text === interfaceName) {
      return statement
    }
  }

  return null
}

function createTsSourceFile(filePath, sourceText) {
  return ts.createSourceFile(
    filePath,
    sourceText,
    ts.ScriptTarget.Latest,
    true,
    filePath.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  )
}

function resolveLocalModule(fromFilePath, moduleSpecifier) {
  if (!moduleSpecifier.startsWith('.') && !moduleSpecifier.startsWith('@/')) {
    return null
  }

  const basePath = moduleSpecifier.startsWith('@/')
    ? path.join(repoRoot, 'src', moduleSpecifier.slice(2))
    : path.resolve(path.dirname(fromFilePath), moduleSpecifier)

  const candidates = [
    basePath,
    `${basePath}.ts`,
    `${basePath}.tsx`,
    `${basePath}.js`,
    `${basePath}.mjs`,
    `${basePath}.cjs`,
    `${basePath}.vue`,
    path.join(basePath, 'index.ts'),
    path.join(basePath, 'index.tsx'),
    path.join(basePath, 'index.js'),
    path.join(basePath, 'index.vue'),
  ]

  return candidates.find((candidate) => {
    if (!fs.existsSync(candidate)) {
      return false
    }

    return fs.statSync(candidate).isFile()
  }) ?? null
}

function inferTokenCategory(filePath, cssVariable) {
  const fileName = path.basename(filePath).toLowerCase()
  if (fileName.includes('color') || cssVariable.includes('color')) {
    return 'color'
  }
  if (fileName.includes('spacing')) {
    return 'spacing'
  }
  if (fileName.includes('radius')) {
    return 'radius'
  }
  if (fileName.includes('shadow')) {
    return 'shadow'
  }
  if (fileName.includes('typography')) {
    return 'typography'
  }
  if (fileName.includes('breakpoint')) {
    return 'breakpoint'
  }
  return 'other'
}

function ensureAnnotationsFile(filePath, fallbackValue) {
  if (!fs.existsSync(filePath)) {
    writeJson(filePath, fallbackValue)
    return fallbackValue
  }

  return JSON.parse(fs.readFileSync(filePath, 'utf8'))
}

function ensureSchemaFile(filePath, fallbackValue) {
  if (!fs.existsSync(filePath)) {
    writeJson(filePath, fallbackValue)
  }
}

function mergeVariants(variants) {
  const variantMap = new Map()

  for (const variant of variants) {
    const existing = variantMap.get(variant.name) ?? { name: variant.name, values: [] }
    const mergedValues = new Set([...existing.values, ...variant.values])
    variantMap.set(variant.name, { name: variant.name, values: Array.from(mergedValues).sort((left, right) => left.localeCompare(right)) })
  }

  return Array.from(variantMap.values()).sort((left, right) => left.name.localeCompare(right.name))
}

function mergePropRecords(baseRecord, overrideRecord) {
  return mergeRecords(baseRecord, overrideRecord)
}

function mergeRecords(baseRecord, overrideRecord) {
  if (!baseRecord) {
    return cloneJsonCompatible(overrideRecord)
  }

  if (!overrideRecord) {
    return cloneJsonCompatible(baseRecord)
  }

  const mergedRecord = { ...baseRecord }

  for (const [key, value] of Object.entries(overrideRecord)) {
    if (Array.isArray(value)) {
      mergedRecord[key] = [...value]
      continue
    }

    if (value && typeof value === 'object') {
      mergedRecord[key] = mergeRecords(baseRecord[key] ?? {}, value)
      continue
    }

    mergedRecord[key] = value
  }

  return mergedRecord
}

function listFiles(rootDir, predicate) {
  if (!fs.existsSync(rootDir)) {
    return []
  }

  const files = []
  const entries = fs.readdirSync(rootDir, { withFileTypes: true })

  for (const entry of entries) {
    const fullPath = path.join(rootDir, entry.name)
    if (entry.isDirectory()) {
      files.push(...listFiles(fullPath, predicate))
      continue
    }

    if (predicate(fullPath)) {
      files.push(fullPath)
    }
  }

  return files.sort((left, right) => left.localeCompare(right))
}

function toRepoPath(filePath) {
  return path.relative(repoRoot, filePath).split(path.sep).join('/')
}

function writeJson(filePath, value) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true })
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`)
}

function extractVueScriptContent(vueSource) {
  const match = vueSource.match(/<script\b[^>]*\bsetup\b[^>]*>([\s\S]*?)<\/script>/)
  return match ? match[1].trim() : ''
}

function extractVueTemplateContent(vueSource) {
  const match = vueSource.match(/<template>([\s\S]*?)<\/template>/)
  return match ? match[1] : ''
}

function getPropertyName(nameNode) {
  if (!nameNode) {
    return null
  }

  if (ts.isIdentifier(nameNode) || ts.isStringLiteral(nameNode) || ts.isNumericLiteral(nameNode)) {
    return nameNode.text
  }

  if (ts.isComputedPropertyName(nameNode) && ts.isStringLiteral(nameNode.expression)) {
    return nameNode.expression.text
  }

  return null
}

function hasModifier(modifiers, modifierKind) {
  return Boolean(modifiers?.some((modifier) => modifier.kind === modifierKind))
}

function unwrapExpression(expression) {
  let current = expression

  while (
    ts.isParenthesizedExpression(current) ||
    ts.isAsExpression(current) ||
    ts.isSatisfiesExpression(current) ||
    ts.isTypeAssertionExpression(current) ||
    ts.isNonNullExpression(current)
  ) {
    current = current.expression
  }

  return current
}

function isPublicComponentName(name) {
  return /^P[A-Z0-9]/.test(name)
}

function isFunctionLikeInitializer(node) {
  return ts.isArrowFunction(node) || ts.isFunctionExpression(node)
}

function toComponentId(componentName) {
  return componentName
    .replace(/^P/, 'p-')
    .replace(/([a-z0-9])([A-Z])/g, '$1-$2')
    .toLowerCase()
}

function slugify(value) {
  return value
    .replace(/[^A-Za-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase()
}

function cloneJsonCompatible(value) {
  if (value === undefined || value === null) {
    return value
  }

  return JSON.parse(JSON.stringify(value))
}

function compactUnique(values) {
  return Array.from(new Set(values.filter(Boolean)))
}

const moduleContextCache = new Map()

export { main }

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main()
}
