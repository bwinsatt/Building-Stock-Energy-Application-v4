import type { VariantProps } from "class-variance-authority"
import { cva } from "class-variance-authority"

export { default as PRadioGroup } from "./PRadioGroup.vue"
export { default as PRadioGroupItem } from "./PRadioGroupItem.vue"
export type { PRadioGroupProps } from "./PRadioGroup.vue"
export type { PRadioGroupItemProps } from "./PRadioGroupItem.vue"

export const radioGroupVariantOptions = ['default', 'rating'] as const

export const radioGroupVariants = cva(
  "partner-preflight relative w-full rounded-sm border data-[removed=true]:hidden",
  {
    variants: {
      variant: {
        default: "",
        rating: "",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
)

export type PRadioGroupVariants = VariantProps<typeof radioGroupVariants>