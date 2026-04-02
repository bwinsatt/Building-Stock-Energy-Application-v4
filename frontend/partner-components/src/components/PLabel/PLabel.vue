<script setup lang="ts">
import '@/styles/global.css'
import { Label } from '@/components/shadcn/ui/label'
import { useTestId } from '@/composables/useTestId'
import { PTypography } from '@/components/PTypography'
import { computed, type HTMLAttributes } from 'vue'
import type { PTypographyVariant, PTypographyComponent } from '@/components/PTypography/types'
import { cn } from '@/lib/utils'

export interface PLabelProps {
  for?: string
  class?: HTMLAttributes['class']
  variant?: PTypographyVariant
  component?: PTypographyComponent
  disabled?: boolean
  required?: boolean
  error?: boolean
}

const props = withDefaults(defineProps<PLabelProps>(), {
  for: '',
  class: '',
  variant: 'inputLabel',
  component: undefined,
})

const { testIdAttrs } = useTestId()

const errorClass = computed(() => props.error ? 'text-(--partner-error-main)' : '')

const disabledClass = computed(() => props.disabled ? 'cursor-not-allowed text-(--partner-text-disabled)' : '')

const disabledErrorClass = computed(() => props.disabled ? 'opacity-50' : '')
</script>

<template>
  <Label
    :for="props.for"
    :class="cn('partner-preflight font-normal text-partner-secondary', errorClass, disabledClass, props.class)"
    v-bind="testIdAttrs"
    :data-disabled="props.disabled"
  >
    <PTypography
      :variant="props.variant"
      :component="props.component"
    >
      <slot />
      <span
        v-if="props.required"
        :class="cn('text-(--partner-error-main)', disabledErrorClass)"
      >*</span>
    </PTypography>
  </Label>
</template>