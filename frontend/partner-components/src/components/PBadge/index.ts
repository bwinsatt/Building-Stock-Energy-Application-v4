import type { VariantProps } from "class-variance-authority"
import { cva } from "class-variance-authority"

const variants = {
  primary: 'bg-partner-blue-7',
  secondary: 'bg-partner-orange-7',
  error: 'bg-partner-red-7',
  warning: 'bg-partner-yellow-7',
  success: 'bg-partner-green-7',
  neutral: 'bg-partner-gray-7 text-partner-white',
} as const

const appearances = {
  standard: 'h-5 w-fit min-w-5 px-1.5',
  dot: 'size-2',
} as const

export const badgeVariants = cva(
  'partner-preflight rounded-full flex items-center justify-center text-(--partner-primary-contrast) bg-partner-gray-5 select-none',
  {
    variants: {
      variant: variants,
      appearance: appearances,
    },
    defaultVariants: {
      variant: 'primary',
      appearance: 'standard',
    },
  },
)

export type BadgeVariants = VariantProps<typeof badgeVariants>

export const badgeOptions = {
  variants: Object.keys(variants),
  appearances: Object.keys(appearances),
}

export { default as PBadge, type PBadgeProps } from './PBadge.vue'