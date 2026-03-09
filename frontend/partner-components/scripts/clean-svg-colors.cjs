#!/usr/bin/env node

/**
 * SVG Color Cleaner
 *
 * This script removes hardcoded colors from SVG files and replaces them with
 * `currentColor` to make them work properly with CSS styling.
 *
 * Usage:
 *   node scripts/clean-svg-colors.cjs
 *
 * or to process a specific directory:
 *   node scripts/clean-svg-colors.cjs src/assets/icons/outline
 */

const fs = require('fs');
const path = require('path');

// Function to clean SVG content
function cleanSvgColors(svgContent) {
  return svgContent
    // Replace common hardcoded gray colors with currentColor
    .replace(/stroke="#858B91"/g, 'stroke="currentColor"')
    .replace(/fill="#858B91"/g, 'fill="currentColor"')

    // Replace other common hardcoded colors (but preserve white and none)
    .replace(/stroke="#[0-9A-Fa-f]{6}"/g, (match) => {
      const color = match.match(/#([0-9A-Fa-f]{6})/)[1].toLowerCase();
      if (color === 'ffffff' || color === 'white') {
        return 'stroke="white"';
      }
      if (color === '000000' || color === 'black') {
        return 'stroke="currentColor"';
      }
      // Replace any other color with currentColor
      return 'stroke="currentColor"';
    })
    .replace(/fill="#[0-9A-Fa-f]{6}"/g, (match) => {
      const color = match.match(/#([0-9A-Fa-f]{6})/)[1].toLowerCase();
      if (color === 'ffffff' || color === 'white') {
        return 'fill="white"';
      }
      if (color === '000000' || color === 'black') {
        return 'fill="currentColor"';
      }
      // Replace any other color with currentColor
      return 'fill="currentColor"';
    })

    // Handle 3-digit hex colors
    .replace(/stroke="#[0-9A-Fa-f]{3}"/g, (match) => {
      const color = match.match(/#([0-9A-Fa-f]{3})/)[1].toLowerCase();
      if (color === 'fff') {
        return 'stroke="white"';
      }
      if (color === '000') {
        return 'stroke="currentColor"';
      }
      return 'stroke="currentColor"';
    })
    .replace(/fill="#[0-9A-Fa-f]{3}"/g, (match) => {
      const color = match.match(/#([0-9A-Fa-f]{3})/)[1].toLowerCase();
      if (color === 'fff') {
        return 'fill="white"';
      }
      if (color === '000') {
        return 'fill="currentColor"';
      }
      return 'fill="currentColor"';
    })

    // Clean up RGB colors
    .replace(/stroke="rgb\([^)]+\)"/g, (match) => {
      if (match.includes('255, 255, 255') || match.includes('255,255,255')) {
        return 'stroke="white"';
      }
      if (match.includes('0, 0, 0') || match.includes('0,0,0')) {
        return 'stroke="currentColor"';
      }
      return 'stroke="currentColor"';
    })
    .replace(/fill="rgb\([^)]+\)"/g, (match) => {
      if (match.includes('255, 255, 255') || match.includes('255,255,255')) {
        return 'fill="white"';
      }
      if (match.includes('0, 0, 0') || match.includes('0,0,0')) {
        return 'fill="currentColor"';
      }
      return 'fill="currentColor"';
    })

    // Clean up named colors (except white and none which we want to preserve)
    .replace(/stroke="(black|gray|grey|red|blue|green|yellow|orange|purple|pink|brown)"/gi, 'stroke="currentColor"')
    .replace(/fill="(black|gray|grey|red|blue|green|yellow|orange|purple|pink|brown)"/gi, 'fill="currentColor"')

    // Preserve important values (these should remain unchanged):
    // fill="none", stroke="none", fill="white", stroke="white"
    ;
}

// Function to process a directory of SVG files
function processSvgDirectory(dirPath) {
  if (!fs.existsSync(dirPath)) {
    console.log(`⚠️  Directory not found: ${dirPath}`);
    return 0;
  }

  const files = fs.readdirSync(dirPath);
  let processedCount = 0;

  files.forEach(file => {
    if (path.extname(file) === '.svg') {
      const filePath = path.join(dirPath, file);
      const originalContent = fs.readFileSync(filePath, 'utf8');
      const cleanedContent = cleanSvgColors(originalContent);

      if (originalContent !== cleanedContent) {
        fs.writeFileSync(filePath, cleanedContent, 'utf8');
        console.log(`✓ Cleaned: ${file}`);
        processedCount++;
      } else {
        console.log(`- No changes needed: ${file}`);
      }
    }
  });

  return processedCount;
}

// Main execution
console.log('🎨 SVG Color Cleaner\n');

// Check if a specific directory was provided as an argument
const targetDir = process.argv[2];

if (targetDir) {
  // Process specific directory
  console.log(`📁 Processing: ${targetDir}`);
  const processed = processSvgDirectory(targetDir);
  console.log(`\n✅ Done! Processed ${processed} files.`);
} else {
  // Process default icon directories
  const outlineDir = path.join(__dirname, '../src/assets/icons/outline');
  const solidDir = path.join(__dirname, '../src/assets/icons/solid');

  console.log('📁 Processing outline icons...');
  const outlineProcessed = processSvgDirectory(outlineDir);

  console.log('\n📁 Processing solid icons...');
  const solidProcessed = processSvgDirectory(solidDir);

  console.log(`\n✅ Done! Processed ${outlineProcessed + solidProcessed} files total.`);
}

console.log('🎉 SVG files are now ready for proper CSS styling!');