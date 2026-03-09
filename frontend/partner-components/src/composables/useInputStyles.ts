// src/composables/useInputStyles.ts
import { computed, type ComputedRef, type HTMLAttributes } from 'vue'
import type { Size } from '@/types/size'
import { cn } from '@/lib/utils'

interface UseInputStylesOptions {
  class?: HTMLAttributes["class"]
  size?: Size
  error?: boolean
  errorText?: string
  disabled?: boolean
  helperText?: string
}

export function useInputStyles(props: UseInputStylesOptions) {
  const helperErrorText = computed(() =>
    props.error && props.errorText ? props.errorText : props.helperText
  ) as ComputedRef<string | undefined>

  const inputClass = computed(() => {
    return cn('flex w-full rounded-sm shadow-none border border-(--partner-border-default) bg-transparent px-3 py-1.5 partner-inputText transition-colors',
                 sizeClass.value,
                 'placeholder:text-(--partner-text-placeholder)',
                 'hover:border-(--partner-border-hovered) focus-visible:border-(--partner-border-active)',
                 'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-(--partner-border-active)',
                 errorClass.value,
                 disabledClass.value,
                 'disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:border-(--partner-border-disabled)',
                 props.class)
  })

  const sizeClass = computed(() => {
    switch (props.size) {
      case 'small':
        return 'h-7 py-1'
      case 'large':
        return 'h-10 py-2.5'
      case 'medium':
      default:
        return 'h-8'
    }
  })

  const errorClass = computed(() =>
    props.error
      ? 'border-(--partner-error-main) focus-visible:border-(--partner-error-main) focus-visible:ring-(--partner-error-main)'
      : ''
  )

  const disabledClass = computed(() =>
    props.disabled
      ? 'border-(--partner-border-disabled) bg-(--partner-fill-disabled) dark:bg-(--partner-fill-disabled)/10'
      : ''
  )

  return { helperErrorText, inputClass, sizeClass, errorClass, disabledClass }
}