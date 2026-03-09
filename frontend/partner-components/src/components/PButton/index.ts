import type { VariantProps } from "class-variance-authority"
import { cva } from "class-variance-authority"

export { default as PButton, type PButtonProps, type PButtonEmits } from "./PButton.vue"

export const buttonVariants = cva(
  "cursor-pointer w-fit inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-sm text-sm font-medium transition-all disabled:pointer-events-none disabled:opacity-100 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive",
  {
    variants: {
      variant: {
        default: "",
        primary: "",
        secondary: "",
        error: "",
        warning: "",
        success: "",
        neutral: "",
        white: "",
      },
      appearance: {
        contained: "",
        outlined: "bg-transparent border",
        text: "bg-transparent border-transparent shadow-none",
        link: "bg-transparent border-transparent shadow-none hover:bg-transparent active:bg-transparent",
      },
      size: {
        "small": "button-small h-6 gap-1 px-2 py-0 has-[>svg]:p-0",
        "medium": "button-medium h-8 gap-1 px-3 py-0 has-[>svg]:p-0",
        "large": "button-large h-10 px-4 py-0 has-[>svg]:p-0",
      },
      iconButton: {
        true: "",
        false: "",
      },
    },
    compoundVariants: [
      {
        iconButton: true,
        size: "small",
        class: "size-6",
      },
      {
        iconButton: true,
        size: "medium",
        class: "size-8",
      },
      {
        iconButton: true,
        size: "large",
        class: "size-10",
      },
      /**
       * Default / Primary
       */
      {
        variant: ["default", "primary"],
        appearance: "contained",
        class: "text-(--partner-primary-contrast) bg-(--partner-primary-main) hover:bg-(--partner-primary-light) active:bg-(--partner-primary-dark) disabled:bg-(--partner-action-disabled)",
      },
      {
        variant: ["default", "primary"],
        appearance: "outlined",
        class: "text-(--partner-primary-main) disabled:text-(--partner-action-disabled) border-(--partner-primary-outlined-border) bg-(--partner-primary-contrast) hover:bg-(--partner-primary-outlined-hovered) active:bg-(--partner-primary-outlined-hover-pressed) disabled:border-(--partner-action-disabled)",
      },
      {
        variant: ["default", "primary"],
        appearance: "text",
        class: "text-(--partner-primary-main) disabled:text-(--partner-action-disabled) hover:bg-(--partner-primary-outlined-hovered) active:bg-(--partner-primary-outlined-hover-pressed)",
      },
      {
        variant: ["default", "primary"],
        appearance: "link",
        class: "text-(--partner-primary-main) disabled:text-(--partner-action-disabled) hover:text-(--partner-primary-light) active:text-(--partner-primary-dark)",
      },
      /**
       * Secondary
       */
      {
        variant: "secondary",
        appearance: "contained",
        class: "text-(--partner-secondary-contrast) bg-(--partner-secondary-main) hover:bg-(--partner-secondary-light) active:bg-(--partner-secondary-dark) disabled:bg-(--partner-action-disabled)",
      },
      {
        variant: "secondary",
        appearance: "outlined",
        class: "text-(--partner-secondary-main) disabled:text-(--partner-action-disabled) border-(--partner-secondary-outlined-border) bg-(--partner-secondary-contrast) hover:bg-(--partner-secondary-outlined-hovered) active:bg-(--partner-secondary-outlined-hover-pressed) disabled:border-(--partner-action-disabled)",
      },
      {
        variant: "secondary",
        appearance: "text",
        class: "text-(--partner-secondary-main) disabled:text-(--partner-action-disabled) hover:bg-(--partner-secondary-outlined-hovered) active:bg-(--partner-secondary-outlined-hover-pressed)",
      },
      {
        variant: "secondary",
        appearance: "link",
        class: "text-(--partner-secondary-main) disabled:text-(--partner-action-disabled) hover:text-(--partner-secondary-light) active:text-(--partner-secondary-dark)",
      },
      /**
       * Error
       */
      {
        variant: "error",
        appearance: "contained",
        class: "text-(--partner-error-contrast) bg-(--partner-error-main) hover:bg-(--partner-error-light) active:bg-(--partner-error-dark) disabled:bg-(--partner-action-disabled)",
      },
      {
        variant: "error",
        appearance: "outlined",
        class: "text-(--partner-error-main) disabled:text-(--partner-action-disabled) border-(--partner-error-outlined-border) bg-(--partner-error-contrast) hover:bg-(--partner-error-outlined-hovered) active:bg-(--partner-error-outlined-hover-pressed) disabled:border-(--partner-action-disabled)",
      },
      {
        variant: "error",
        appearance: "text",
        class: "text-(--partner-error-main) disabled:text-(--partner-action-disabled) hover:bg-(--partner-error-outlined-hovered) active:bg-(--partner-error-outlined-hover-pressed)",
      },
      {
        variant: "error",
        appearance: "link",
        class: "text-(--partner-error-main) disabled:text-(--partner-action-disabled) hover:text-(--partner-error-light) active:text-(--partner-error-dark)",
      },
      /**
       * Warning
       */
      {
        variant: "warning",
        appearance: "contained",
        class: "text-(--partner-warning-contrast) bg-(--partner-warning-main) hover:bg-(--partner-warning-light) active:bg-(--partner-warning-dark) disabled:bg-(--partner-action-disabled)",
      },
      {
        variant: "warning",
        appearance: "outlined",
        class: "text-(--partner-warning-main) disabled:text-(--partner-action-disabled) border-(--partner-warning-outlined-border) bg-(--partner-warning-contrast) hover:bg-(--partner-warning-outlined-hovered) active:bg-(--partner-warning-outlined-hover-pressed) disabled:border-(--partner-action-disabled)",
      },
      {
        variant: "warning",
        appearance: "text",
        class: "text-(--partner-warning-main) disabled:text-(--partner-action-disabled) hover:bg-(--partner-warning-outlined-hovered) active:bg-(--partner-warning-outlined-hover-pressed)",
      },
      {
        variant: "warning",
        appearance: "link",
        class: "text-(--partner-warning-main) disabled:text-(--partner-action-disabled) hover:text-(--partner-warning-light) active:text-(--partner-warning-dark)",
      },
      /**
       * Success
       */
      {
        variant: "success",
        appearance: "contained",
        class: "text-(--partner-success-contrast) bg-(--partner-success-main) hover:bg-(--partner-success-light) active:bg-(--partner-success-dark) disabled:bg-(--partner-action-disabled)",
      },
      {
        variant: "success",
        appearance: "outlined",
        class: "text-(--partner-success-main) disabled:text-(--partner-action-disabled) border-(--partner-success-outlined-border) bg-(--partner-success-contrast) hover:bg-(--partner-success-outlined-hovered) active:bg-(--partner-success-outlined-hover-pressed) disabled:border-(--partner-action-disabled)",
      },
      {
        variant: "success",
        appearance: "text",
        class: "text-(--partner-success-main) disabled:text-(--partner-action-disabled) hover:bg-(--partner-success-outlined-hovered) active:bg-(--partner-success-outlined-hover-pressed)",
      },
      {
        variant: "success",
        appearance: "link",
        class: "text-(--partner-success-main) disabled:text-(--partner-action-disabled) hover:text-(--partner-success-light) active:text-(--partner-success-dark)",
      },
      /**
       * Neutral
       * Does not have a defined contained appearance in the design system
       */
      {
        variant: "neutral",
        appearance: "outlined",
        class: "text-partner dark:disabled:opacity-50 disabled:text-(--partner-action-disabled) border-(--partner-inherit-border) disabled:border-(--partner-action-disabled) bg-transparent hover:bg-(--partner-inherit-hovered) active:bg-(--partner-inherit-hover-pressed)",
      },
      {
        variant: "neutral",
        appearance: "text",
        class: "text-partner dark:disabled:opacity-50 disabled:text-(--partner-action-disabled) hover:bg-(--partner-inherit-hovered) active:bg-(--partner-inherit-hover-pressed)",
      },
      {
        variant: "neutral",
        appearance: "link",
        class: "text-partner dark:disabled:opacity-50 disabled:text-(--partner-inherit-disabled) hover:text-(--partner-inherit-border) active:text-(--partner-inherit-main)",
      },
      /**
       * White
       * Does not have a defined contained appearance in the design system
       */
      {
        variant: "white",
        appearance: "outlined",
        class: "text-white disabled:text-(--partner-action-disabled) border-(--partner-inherit-white-border) bg-(--partner-inherit-white-contrast) hover:bg-(--partner-inherit-white-hovered) active:bg-(--partner-inherit-white-hover-pressed) disabled:border-(--partner-action-disabled)",
      },
      {
        variant: "white",
        appearance: "text",
        class: "text-white disabled:text-(--partner-action-disabled) hover:bg-(--partner-inherit-white-hovered) active:bg-(--partner-inherit-white-hover-pressed)",
      },
      {
        variant: "white",
        appearance: "link",
        class: "text-white disabled:text-(--partner-inherit-white-disabled) hover:text-(--partner-inherit-white-border) active:text-(--partner-inherit-white-hovered)",
      },
    ],
    defaultVariants: {
      variant: "primary",
      size: "medium",
      appearance: "contained",
      iconButton: false,
    },
  },
)
export type ButtonVariants = VariantProps<typeof buttonVariants>