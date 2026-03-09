#!/usr/bin/env node

import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

console.log('🧪 Testing Partner Components Sample App Build')
console.log('=============================================')

// Check if the library is built
const libraryPath = path.join(__dirname, '../../dist')
const cssFile = path.join(libraryPath, 'partner-components.css')
const jsFile = path.join(libraryPath, 'p-components.es.js')

console.log('\n📦 Checking library build...')
if (fs.existsSync(cssFile)) {
  console.log('✅ CSS file exists:', cssFile)
} else {
  console.log('❌ CSS file missing:', cssFile)
  process.exit(1)
}

if (fs.existsSync(jsFile)) {
  console.log('✅ JS file exists:', jsFile)
} else {
  console.log('❌ JS file missing:', jsFile)
  process.exit(1)
}

// Check if node_modules exists
const nodeModulesPath = path.join(__dirname, 'node_modules')
console.log('\n📥 Checking dependencies...')
if (fs.existsSync(nodeModulesPath)) {
  console.log('✅ node_modules exists')
} else {
  console.log('❌ node_modules missing - run npm install')
  process.exit(1)
}

// Check if partner-components is linked
const partnerComponentsPath = path.join(nodeModulesPath, 'partner-components')
if (fs.existsSync(partnerComponentsPath)) {
  console.log('✅ partner-components package linked')
} else {
  console.log('❌ partner-components package not found')
  process.exit(1)
}

console.log('\n✅ All checks passed!')
console.log('\nTo start the development server:')
console.log('  npm run dev')
console.log('\nTo build for production:')
console.log('  npm run build')