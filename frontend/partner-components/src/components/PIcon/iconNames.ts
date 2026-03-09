import { getIconNames } from './icons'
import { getCarbonIconNames } from './carbonIcons'

// Create options with visual separation using dividers
const customIcons = getIconNames()
const carbonIcons = getCarbonIconNames()
const DIVIDER_PARTNER = '━━━ Partner Components Icons ━━━'
const DIVIDER_CARBON = '━━━ Carbon Icons (Fallback) ━━━'

const iconOptions = [
  DIVIDER_PARTNER,
  ...customIcons,
  DIVIDER_CARBON,
  ...carbonIcons,
]

// Check if an icon name is a custom Partner Components icon
function isCustomIcon(name: string): boolean {
  return customIcons.includes(name)
}

// Strip dividers and return the icon name, or return first valid icon if divider is selected
function normalizeIconName(name: string): string {
  if (name === DIVIDER_PARTNER || name === DIVIDER_CARBON) {
    // If a divider is selected, default to first custom icon
    return customIcons[0] || carbonIcons[0] || ''
  }
  return name
}

export { 
  customIcons, 
  carbonIcons, 
  iconOptions, 
  isCustomIcon, 
  normalizeIconName,
}