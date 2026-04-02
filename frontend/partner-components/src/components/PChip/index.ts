import type { VariantProps } from "class-variance-authority"
import { cva } from "class-variance-authority"

export { default as PChip, type PChipProps, type PChipEmits } from "./PChip.vue"

export const chipVariants = cva(
  "partner-preflight inline-flex gap-1 items-center whitespace-nowrap rounded-(--partner-radius-full) border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 data-[selected=true]:border-2 data-[selected=true]:data-[disabled=true]:border-(--partner-border-disabled)",
  {
    variants: {
      variant: {
        default: "text-(--partner-primary-content) data-[selected=true]:border-(--partner-primary-dark)",
        primary: "text-(--partner-primary-content) data-[selected=true]:border-(--partner-primary-dark)",
        secondary: "text-(--partner-secondary-content) data-[selected=true]:border-(--partner-secondary-dark)",
        error: "text-(--partner-error-content) data-[selected=true]:border-(--partner-error-dark)",
        warning: "text-(--partner-warning-content) data-[selected=true]:border-(--partner-warning-dark)",
        success: "text-(--partner-success-content) data-[selected=true]:border-(--partner-success-dark)",
        neutral: "text-(--partner-text-primary) data-[selected=true]:border-(--partner-action-enabled)",
      },
      appearance: {
        contained: "border-transparent text-(--partner-text-white) data-[disabled=true]:text-(--partner-text-disabled) data-[disabled=true]:bg-(--partner-fill-disabled)",
        soft: "border-transparent data-[disabled=true]:text-(--partner-text-disabled) data-[disabled=true]:bg-(--partner-fill-disabled)",
        outlined: "border bg-(--partner-background-white) data-[disabled=true]:text-(--partner-text-disabled) data-[disabled=true]:border-(--partner-border-disabled)",
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
        class: "bg-(--partner-primary-light) hover:bg-(--partner-primary-main)",
      },
      {
        variant: ["default", "primary"],
        appearance: "soft",
        class: "bg-(--partner-primary-outlined-hovered) hover:bg-(--partner-primary-outlined-hover-pressed)",
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
        class: "bg-(--partner-secondary-light) hover:bg-(--partner-secondary-main)",
      },
      {
        variant: ["secondary"],
        appearance: "soft",
        class: "bg-(--partner-secondary-outlined-hovered) hover:bg-(--partner-secondary-outlined-hover-pressed)",
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
        class: "bg-(--partner-error-light) hover:bg-(--partner-error-main)",
      },
      {
        variant: ["error"],
        appearance: "soft",
        class: "bg-(--partner-error-outlined-hovered) hover:bg-(--partner-error-outlined-hover-pressed)",
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
        class: "bg-(--partner-warning-light) hover:bg-(--partner-warning-main)",
      },
      {
        variant: ["warning"],
        appearance: "soft",
        class: "bg-(--partner-warning-outlined-hovered) hover:bg-(--partner-warning-outlined-hover-pressed)",
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
        class: "bg-(--partner-success-light) hover:bg-(--partner-success-main)",
      },
      {
        variant: ["success"],
        appearance: "soft",
        class: "bg-(--partner-success-outlined-hovered) hover:bg-(--partner-success-outlined-hover-pressed)",
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
        class: "bg-(--partner-text-secondary) hover:bg-(--partner-action-enabled)",
      },
      {
        variant: ["neutral"],
        appearance: "soft",
        class: "bg-(--partner-fill-hovered) hover:bg-(--partner-fill-pressed)",
      },
      {
        variant: ["neutral"],
        appearance: "outlined",
        class: "border-(--partner-border-default) hover:bg-(--partner-fill-hovered)",
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
