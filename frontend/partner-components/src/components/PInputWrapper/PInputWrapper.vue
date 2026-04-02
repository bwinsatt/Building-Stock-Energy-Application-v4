<script setup lang="ts">
import '@/styles/global.css'
import { type HTMLAttributes } from 'vue'
import { PLabel } from '@/components/PLabel'
import { useTestId } from '@/composables/useTestId'
import { useInputStyles } from '@/composables/useInputStyles'

export interface PInputWrapperProps {
  class?: HTMLAttributes['class']
  label?: string
  id?: string
  required?: boolean
  disabled?: boolean
  error?: boolean
  errorText?: string
  helperText?: string
}

const props = defineProps<PInputWrapperProps>()

const { testIdAttrs } = useTestId()

const { helperErrorText } = useInputStyles(props)
</script>

<template>
  <div
    class="partner-preflight flex flex-col gap-1"
    v-bind="testIdAttrs"
  >
    <div class="flex flex-row justify-between gap-2">
      <PLabel
        v-if="props.label"
        :for="props.id"
        :required="props.required"
        :disabled="props.disabled"
        :error="props.error"
      >
        <slot name="label">
          {{ props.label }}
        </slot>
      </PLabel>
      <slot name="label-right" />
    </div>
    <slot />
    <PLabel
      v-if="helperErrorText"
      :disabled="props.disabled" 
      :error="props.error"
    >
      {{ helperErrorText }}
    </PLabel>
  </div>
</template>