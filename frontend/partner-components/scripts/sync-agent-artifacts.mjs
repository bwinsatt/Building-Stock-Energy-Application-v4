import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

function main() {
  const repoRoot = process.cwd()
  const sourceDocPath = path.join(repoRoot, 'docs', 'ai-artifacts.md')
  const publicDocPath = path.join(repoRoot, 'agent-artifacts', 'exports', 'ai-artifacts.md')
  const figmaSourceDir = path.join(repoRoot, 'agent-artifacts', 'source')
  const publicExportsDir = path.join(repoRoot, 'agent-artifacts', 'exports')
  const figmaArtifactFiles = [
    'figma-component-map.json',
    'figma-mapping-hints.json',
  ]

  fs.mkdirSync(publicExportsDir, { recursive: true })
  fs.copyFileSync(sourceDocPath, publicDocPath)

  for (const fileName of figmaArtifactFiles) {
    const sourcePath = path.join(figmaSourceDir, fileName)
    const publicPath = path.join(publicExportsDir, fileName)

    if (!fs.existsSync(sourcePath)) {
      throw new Error(`Missing curated Figma artifact source: ${toRepoPath(repoRoot, sourcePath)}`)
    }

    fs.copyFileSync(sourcePath, publicPath)
  }

  console.log(`Synced ${toRepoPath(repoRoot, sourceDocPath)} -> ${toRepoPath(repoRoot, publicDocPath)}`)
  for (const fileName of figmaArtifactFiles) {
    console.log(
      `Synced ${toRepoPath(repoRoot, path.join(figmaSourceDir, fileName))} -> ${toRepoPath(repoRoot, path.join(publicExportsDir, fileName))}`,
    )
  }
}

function toRepoPath(repoRoot, filePath) {
  return path.relative(repoRoot, filePath) || '.'
}

export { main }

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main()
}
