import type { Size } from '@/types/size'

export { default as PCheckbox } from "./PCheckbox.vue"
export { default as PCheckboxGroup } from "./PCheckboxGroup.vue"

export type CheckedState = boolean | 'indeterminate' | null

export interface PCheckboxProps {
  label?: string
  id?: string
  checked?: boolean
  disabled?: boolean
  indeterminate?: boolean
  required?: boolean
  size?: Size
  class?: string
  onChange?: (value: CheckedState) => void
}

export interface PCheckboxEmits {
  'changed': [value: CheckedState]
}

export interface PCheckboxGroupItemProps {
  label?: string
  id?: string
  checked?: boolean
  disabled?: boolean
}

export interface PCheckboxGroupProps {
  label?: string
  checkboxes: PCheckboxProps[]
  orientation?: 'vertical' | 'horizontal'
  disabled?: boolean
  required?: boolean
  size?: Size
  class?: string
  error?: boolean
  helperText?: string
  errorText?: string
  onChange?: (checkboxes: PCheckboxGroupItemProps[]) => void
}

export interface PCheckboxGroupEmits {
  'changed': [checkboxes: PCheckboxGroupItemProps[]]
}