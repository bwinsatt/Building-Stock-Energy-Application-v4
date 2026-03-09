/**
 * Find an icon SVG file by name
 * Searches in both outline and solid directories
 */

// Import all SVG files from both directories
const iconFiles = import.meta.glob('/src/assets/icons/*.svg', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

// Build a normalized lookup map once (O(1) lookups)
const iconMap = new Map<string, string>()
for (const [path, content] of Object.entries(iconFiles)) {
  const fileName = path.split('/').pop()?.replace('.svg', '').toLowerCase()
  if (fileName) {
    iconMap.set(fileName, content)
  }
}

/**
 * Replace all color values in SVG with currentColor
 * @param svg - SVG content as string
 * @returns SVG with colors replaced by currentColor
 */
export function replaceColors(svg: string): string {
  return svg
    // Replace fill colors (hex, rgb, rgba, hsl, hsla, named colors)
    .replace(/fill="(?!none|currentColor)[^"]*"/g, 'fill="currentColor"')
    // Replace stroke colors
    .replace(/stroke="(?!none|currentColor)[^"]*"/g, 'stroke="currentColor"')
}

/**
 * Find an icon by name and style
 * @param name - Icon name (case-insensitive)
 * @returns SVG content as string, or null if not found
 */
export function findIcon(name: string): string | null {
  const svg = iconMap.get(name.toLowerCase())
  return svg ? replaceColors(svg) : null
}

export function getIconNames(): string[] {
  return Array.from(iconMap.keys())
}