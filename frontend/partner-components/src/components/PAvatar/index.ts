export { default as PAvatar, 
  type PAvatarProps,
  type PAvatarSize,
  type PAvatarShape,
  type PAvatarBadge,
  type PAvatarBadgePosition,
} from './PAvatar.vue'
export { default as PAvatarGroup, type PAvatarGroupProps } from './PAvatarGroup.vue'

export const avatarOptions = {
  sizes: ['small', 'medium', 'large', 'xlarge'],
  shapes: ['circle', 'square'],
  spacing: ['none', 'default', 'compact'],
  badges: [
    'primary', 'secondary', 'success', 'warning', 'error', 'neutral',
    'online', 'green',
    'away', 'yellow',
    'busy', 'red',
    'offline', 'gray',
    'blue', 'orange',
  ],
  badgePositions: [
    'top-left',
    'top-right',
    'bottom-left',
    'bottom-right',
  ],
}