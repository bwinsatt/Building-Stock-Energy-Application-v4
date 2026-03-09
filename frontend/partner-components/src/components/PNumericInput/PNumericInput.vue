<script setup lang="ts">
import '@/styles/global.css'
import { type HTMLAttributes } from 'vue'
import { cn } from '@/lib/utils'
import { PLabel } from '@/components/PLabel/'
import {
  NumberField,
  NumberFieldContent,
  NumberFieldDecrement,
  NumberFieldIncrement,
  NumberFieldInput,
} from '@/components/PNumericInput/number-field'
import { useTestId } from '@/composables/useTestId'
import type { Size } from '@/types/size'
import { useInputStyles } from '@/composables/useInputStyles'
import { generateTestId } from '@/utils/testId'

export interface PNumericInputProps {
  class?: HTMLAttributes["class"]
  defaultValue?: number
  modelValue?: number | null
  /** The smallest value allowed for the input. */
  min?: number
  /** The largest value allowed for the input. */
  max?: number
  /** The amount that the input value changes with each increment or decrement "tick". */
  step?: number
  /** When `false`, prevents the value from snapping to the nearest increment of the step value */
  stepSnapping?: boolean
  /** When `true`, the input will be focused when the value changes. */
  focusOnChange?: boolean
  /** Formatting options for the value displayed in the number field. This also affects what characters are allowed to be typed by the user. */
  formatOptions?: Intl.NumberFormatOptions
  /** The locale to use for formatting and currencies */
  locale?: string
  /** When `true`, prevents the user from interacting with the Number Field. */
  disabled?: boolean
  /** When `true`, the Number Field is read-only. */
  readonly?: boolean
  /** When `true`, prevents the value from changing on wheel scroll. */
  disableWheelChange?: boolean
  /** When `true`, inverts the direction of the wheel change. */
  invertWheelChange?: boolean
  /** Id of the element */
  id?: string

  size?: Size
  required?: boolean
  label?: string
  error?: boolean
  errorText?: string
  helperText?: string
}

const props = withDefaults(defineProps<PNumericInputProps>(), {
  locale: 'en-US',
})

export interface PNumericInputEmits {
  (e: "update:modelValue", payload: number): void
  (e: "focus", payload: FocusEvent): void
  (e: "blur", payload: FocusEvent): void
}

const emits = defineEmits<PNumericInputEmits>()

const { testIdAttrs } = useTestId()

const { helperErrorText, inputClass } = useInputStyles(props)
</script>

<template>
  <NumberField
    v-bind="{...testIdAttrs, ...props}"
    :class="cn('flex flex-col gap-1')"
    @update:model-value="emits('update:modelValue', $event)"
  >
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
    <NumberFieldContent>
      <NumberFieldDecrement v-if="props.step" />
      <NumberFieldInput 
        :data-testid="generateTestId('PNumericInput', 'input')"
        :class="inputClass"
        @focus="emits('focus', $event)"
        @blur="emits('blur', $event)"
      />
      <NumberFieldIncrement v-if="props.step" />
    </NumberFieldContent>
    <PLabel
      v-if="helperErrorText"
      :disabled="props.disabled" 
      :error="props.error"
    >
      {{ helperErrorText }}
    </PLabel>
  </NumberField>
</template>
