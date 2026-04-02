import type { VariantProps } from "class-variance-authority"
import { cva } from "class-variance-authority"

export { default as PAlert, type PAlertProps, type PAlertEmits } from "./PAlert.vue"
export const alertVariantOptions = ['default', 'primary', 'info', 'secondary', 'error', 'warning', 'success', 'neutral'] as const
export const alertAppearanceOptions = ['contained', 'outlined', 'underline'] as const
export const alertAlignOptions = ['start', 'center', 'end'] as const

export const alertVariants = cva(
  "partner-preflight relative w-full rounded-sm border data-[removed=true]:hidden",
  {
    variants: {
      variant: {
        default: "",
        info: "",
        primary: "",
        secondary: "",
        error: "",
        warning: "",
        success: "",
        neutral: "",
      },
      appearance: {
        contained: "",
        outlined: "border",
        underline: "rounded-none border-t-0 border-x-0 border-b !border-(--partner-border-light)",
      },
      size: {
        "small": "px-2 py-0.5",
        "medium": "px-3 py-1",
        "large": "px-4 py-1",
      },
    },
    compoundVariants: [
      /**
       * Default / Primary
       */
      {
        variant: ["default", "primary", "info"],
        appearance: "contained",
        class: "text-(--partner-primary-contrast) bg-(--partner-primary-main) [&_svg]:text-(--partner-primary-contrast)",
      },
      {
        variant: ["default", "primary", "info"],
        appearance: ["outlined", "underline"],
        class: "text-(--partner-primary-main) border-(--partner-primary-outlined-border) bg-(--partner-primary-outlined-hovered) [&_svg]:text-(--partner-primary-main)",
      },
      /**
       * Secondary
       */
      {
        variant: ["secondary"],
        appearance: "contained",
        class: "text-(--partner-secondary-contrast) bg-(--partner-secondary-main) [&_svg]:text-(--partner-secondary-contrast)",
      },
      {
        variant: ["secondary"],
        appearance: ["outlined", "underline"],
        class: "text-(--partner-secondary-main) border-(--partner-secondary-outlined-border) bg-(--partner-secondary-outlined-hovered) [&_svg]:text-(--partner-secondary-main)",
      },
      /**
       * Error
       */
      {
        variant: ["error"],
        appearance: "contained",
        class: "text-(--partner-error-contrast) bg-(--partner-error-main) [&_svg]:text-(--partner-error-contrast)",
      },
      {
        variant: ["error"],
        appearance: ["outlined", "underline"],
        class: "text-(--partner-error-main) border-(--partner-error-outlined-border) bg-(--partner-error-outlined-hovered) [&_svg]:text-(--partner-error-main)",
      },
      /**
       * Warning
       */
      {
        variant: ["warning"],
        appearance: "contained",
        class: "text-(--partner-warning-contrast) bg-(--partner-warning-main) [&_svg]:text-(--partner-warning-contrast)",
      },
      {
        variant: ["warning"],
        appearance: ["outlined", "underline"],
        class: "text-(--partner-warning-main) border-(--partner-warning-outlined-border) bg-(--partner-warning-outlined-hovered) [&_svg]:text-(--partner-warning-main)",
      },
      /**
       * Success
       */
      {
        variant: ["success"],
        appearance: "contained",
        class: "text-(--partner-success-contrast) bg-(--partner-success-main) [&_svg]:text-(--partner-success-contrast)",
      },
      {
        variant: ["success"],
        appearance: ["outlined", "underline"],
        class: "text-(--partner-success-main) border-(--partner-success-outlined-border) bg-(--partner-success-outlined-hovered) [&_svg]:text-(--partner-success-main)",
      },
      /**
       * Neutral
       */
      {
        variant: ["neutral"],
        appearance: "contained",
        class: "text-(--partner-text-white) bg-(--partner-inherit-black-main) [&_svg]:text-(--partner-text-white)",
      },
      {
        variant: ["neutral"],
        appearance: ["outlined", "underline"],
        class: "text-(--partner-text-primary) border-(--partner-border-light) bg-(--partner-background-gray) [&_svg]:text-(--partner-text-primary)",
      },
    ],
    defaultVariants: {
      variant: "default",
      appearance: "contained",
      size: "medium",
    },
  },
)

export type PAlertVariants = VariantProps<typeof alertVariants>
