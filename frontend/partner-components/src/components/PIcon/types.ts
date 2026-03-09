import type { Size } from '@/types/size'
import type { HTMLAttributes } from 'vue'

export interface PIconProps {
  class?: HTMLAttributes['class'],
  name: string,
  width?: IconSize,
  height?: IconSize,
  size?: IconSize,
  color?: string,
}

export type IconSize = Size | number | string

export const sizeMap = Object.freeze({
  small: '16px',
  medium: '24px',
  large: '32px',
} as const)