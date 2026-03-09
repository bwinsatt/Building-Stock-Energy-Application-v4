import type { HTMLAttributes } from 'vue'

export interface TypographyProps {
  class?: HTMLAttributes['class'],
  variant: TypographyVariant,
  align?: TypographyAlign,
  component?: TypographyComponent,
  noWrap?: boolean,
  truncate?: boolean,
}

export const typographyVariants = [
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'headline1', 'headline2', 'headline3', 'body1', 'body2', 
  'buttonLarge', 'buttonMedium', 'buttonSmall', 'inputText', 'inputLabel', 'helperText', 'subhead', 'tooltip'
] as const
export type TypographyVariant = (typeof typographyVariants)[number]

export const typographyComponents = [
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'span', 'p', 'small', 'button', 'textarea'
] as const
export type TypographyComponent = (typeof typographyComponents)[number]

export const typographyAligns = ['center', 'inherit', 'justify', 'left', 'right'] as const
export type TypographyAlign = (typeof typographyAligns)[number]