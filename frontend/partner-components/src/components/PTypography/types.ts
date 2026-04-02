import type { HTMLAttributes } from 'vue'

export interface PTypographyProps {
  class?: HTMLAttributes['class'],
  variant: PTypographyVariant,
  align?: PTypographyAlign,
  component?: PTypographyComponent,
  noWrap?: boolean,
  truncate?: boolean,
}

export const typographyVariants = [
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'headline1', 'headline2', 'headline3', 'body1', 'body2', 
  'buttonLarge', 'buttonMedium', 'buttonSmall', 'inputText', 'inputLabel', 'helperText', 'subhead', 'tooltip'
] as const
export type PTypographyVariant = (typeof typographyVariants)[number]

export const typographyComponents = [
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'span', 'p', 'small', 'button', 'textarea'
] as const
export type PTypographyComponent = (typeof typographyComponents)[number]

export const typographyAligns = ['center', 'inherit', 'justify', 'left', 'right'] as const
export type PTypographyAlign = (typeof typographyAligns)[number]