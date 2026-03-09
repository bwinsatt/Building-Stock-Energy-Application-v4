/** Utility functions for working with strings */

export function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return ''
  const first = parts[0][0] ?? ''
  if (parts.length === 1) return first.toUpperCase()
  const last = parts[parts.length - 1][0] ?? ''
  return (first + last).toUpperCase()
}