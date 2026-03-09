import carbonData from './carbon-icons.json' with { type: 'json' }

// Extract all icon names from the local JSON file (includes categories + hidden icons)
const carbonIconNames: string[] = [
  ...Object.values(carbonData.categories as Record<string, string[]>).flat(),
  ...(carbonData.hidden || []),
].sort()

/**
 * Get all available Carbon icon names from Iconify
 * Returns 2,404+ Carbon icon names loaded from local JSON file
 * @returns Array of Carbon icon names (without 'carbon:' prefix)
 */
export function getCarbonIconNames(): string[] {
  return carbonIconNames
}

/**
 * Fetch Carbon icon names from the Iconify API (alternative method)
 * This is an alternative to reading from the local JSON file
 * @returns Promise that resolves to array of Carbon icon names
 */
export async function fetchCarbonIconNamesFromAPI(): Promise<string[]> {
  try {
    const response = await fetch('https://api.iconify.design/collection?prefix=carbon')
    if (response.ok) {
      const data = await response.json()
      // Extract icon names from the categories object and hidden array
      const icons: string[] = [
        ...Object.values(data.categories as Record<string, string[]>).flat(),
        ...(data.hidden || []),
      ]
      return icons.sort()
    }
  } catch (error) {
    console.warn('Failed to fetch Carbon icons from Iconify API:', error)
  }
  return []
}