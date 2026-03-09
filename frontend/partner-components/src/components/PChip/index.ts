import type { VariantProps } from "class-variance-authority"
import { cva } from "class-variance-authority"

export { default as PChip, type PChipProps, type PChipEmits } from "./PChip.vue"

export const chipVariants = cva(
  "inline-flex gap-1 items-center rounded-(--partner-radius-full) border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default: "text-(--partner-primary-content) data-[selected=true]:bg-(--partner-primary-main)",
        primary: "text-(--partner-primary-content) data-[selected=true]:bg-(--partner-primary-main)",
        secondary: "text-(--partner-secondary-content) data-[selected=true]:bg-(--partner-secondary-main)",
        error: "text-(--partner-error-content) data-[selected=true]:bg-(--partner-error-main)",
        warning: "text-(--partner-warning-content) data-[selected=true]:bg-(--partner-warning-main)",
        success: "text-(--partner-success-content) data-[selected=true]:bg-(--partner-success-main)",
        neutral: "text-(--partner-text-primary) data-[selected=true]:bg-(--partner-gray-7)",
      },
      appearance: {
        contained: "border-transparent data-[selected=true]:text-(--partner-text-white) data-[disabled=true]:text-(--partner-text-disabled) data-[disabled=true]:bg-(--partner-fill-disabled)",
        outlined: "border bg-(--partner-white) data-[selected=true]:border-transparent data-[selected=true]:text-(--partner-text-white) data-[disabled=true]:text-(--partner-text-disabled) data-[disabled=true]:border-(--partner-border-disabled)",
      },  
      size: {
        "small": "h-5 gap-1 px-2 py-0.5",
        "medium": "h-6.5 gap-1 px-2 py-0.5",
        "large": "h-8.5 gap-1 px-3 py-0.5",
      },
    },
    compoundVariants: [
      /**
       * Default / Primary
       */
      {
        variant: ["default", "primary"],
        appearance: "contained",
        class: "bg-(--partner-blue-1) hover:bg-(--partner-blue-2)",
      },
      {
        variant: ["default", "primary"],
        appearance: "outlined",
        class: "border-(--partner-blue-4) hover:bg-(--partner-primary-outlined-hovered)",
      },
      /**
       * Secondary
       */
      {
        variant: ["secondary"],
        appearance: "contained",
        class: "bg-(--partner-orange-1) hover:bg-(--partner-orange-2)",
      },
      {
        variant: ["secondary"],
        appearance: "outlined",
        class: "border-(--partner-orange-4) hover:bg-(--partner-secondary-outlined-hovered)",
      },
      /**
       * Error
       */
      {
        variant: ["error"],
        appearance: "contained",
        class: "bg-(--partner-red-1) hover:bg-(--partner-red-2)",
      },
      {
        variant: ["error"],
        appearance: "outlined",
        class: "border-(--partner-red-4) hover:bg-(--partner-secondary-outlined-hovered)",
      },
      /**
       * Warning
       */
      {
        variant: ["warning"],
        appearance: "contained",
        class: "bg-(--partner-yellow-1) hover:bg-(--partner-yellow-2)",
      },
      {
        variant: ["warning"],
        appearance: "outlined",
        class: "border-(--partner-yellow-4) hover:bg-(--partner-warning-outlined-hovered)",
      },
      /**
       * Success
       */
      {
        variant: ["success"],
        appearance: "contained",
        class: "bg-(--partner-green-1) hover:bg-(--partner-green-2)",
      },
      {
        variant: ["success"],
        appearance: "outlined",
        class: "border-(--partner-green-4) hover:bg-(--partner-success-outlined-hovered)",
      },
      /**
       * Neutral
       */
      {
        variant: ["neutral"],
        appearance: "contained",
        class: "bg-(--partner-gray-2) hover:bg-(--partner-gray-3)",
      },
      {
        variant: ["neutral"],
        appearance: "outlined",
        class: "border-(--partner-gray-7) hover:bg-(--partner-fill-hover)",
      },
    ],
    defaultVariants: {
      variant: "primary",
      size: "medium",
      appearance: "contained",
    },
  },
)

export type ChipVariants = VariantProps<typeof chipVariants>
