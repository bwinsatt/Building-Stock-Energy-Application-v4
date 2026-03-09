/**
 * Sanitizes a string to be used in a test ID
 * - Converts to lowercase
 * - Replaces spaces and special characters with dashes
 * - Removes multiple consecutive dashes
 * - Trims dashes from start and end
 */
function sanitizeTestIdPart(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-') // Replace non-alphanumeric with dashes
    .replace(/-+/g, '-') // Replace multiple dashes with single dash
    .replace(/^-|-$/g, '') // Remove leading/trailing dashes
}

/**
 * Generates a predictable, sanitized test ID from component parts
 * @param parts - Array of strings to join (falsy values are filtered out)
 * @returns A kebab-case test ID string
 * 
 * @example
 * generateTestId('PButton', 'submit') // 'pbutton-submit'
 * generateTestId('PLogo', undefined, 'sitelynx') // 'plogo-sitelynx'
 * generateTestId('PTable', 'User List', 'row-1') // 'ptable-user-list-row-1'
 */
export function generateTestId(...parts: (string | undefined | null)[]): string {
  return parts
    .filter(Boolean)
    .map(part => sanitizeTestIdPart(part as string))
    .filter(Boolean) // Remove any parts that became empty after sanitization
    .join('-')
}