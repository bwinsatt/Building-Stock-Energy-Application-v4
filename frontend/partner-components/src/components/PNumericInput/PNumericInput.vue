<script setup lang="ts">
import '@/styles/global.css'
import { computed, type HTMLAttributes, type ComputedRef } from 'vue'
import { cn } from '@/lib/utils'
import { PInputWrapper } from '@/components/PInputWrapper'
import {
  NumberField,
  NumberFieldContent,
  NumberFieldDecrement,
  NumberFieldIncrement,
  NumberFieldInput,
} from '@/components/PNumericInput/number-field'
import { useVModel } from '@vueuse/core'
import { useTestId } from '@/composables/useTestId'
import type { Size } from '@/types/size'
import { useInputStyles } from '@/composables/useInputStyles'
import { generateTestId } from '@/utils/testId'
import { PButton } from '@/components/PButton'
import { reactiveOmit } from '@vueuse/core'

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
  placeholder?: string
  required?: boolean
  label?: string
  error?: boolean
  errorText?: string
  helperText?: string
  clearable?: boolean
}

const props = withDefaults(defineProps<PNumericInputProps>(), {
  locale: 'en-US',
  disableWheelChange: true,
})

const delegatedProps = reactiveOmit(props, 'class', 'defaultValue', 'modelValue')

export interface PNumericInputEmits {
  (e: "update:modelValue", payload: number | null): void
  (e: "focus", payload: FocusEvent): void
  (e: "blur", payload: FocusEvent): void
}

const emits = defineEmits<PNumericInputEmits>()

const modelValue = useVModel(props, 'modelValue', emits, {
  passive: true,
  defaultValue: props.defaultValue,
})

let inputEmpty: boolean = false

const onClear = () => {
  inputEmpty = true
  modelValue.value = null
}

const onInput = (e: Event) => {
  inputEmpty = !(e.target as HTMLInputElement).value.trim()
}

const isPercentBugCoercion = (next: number | null) =>
  inputEmpty && next === 0 && props.formatOptions?.style === 'percent'

const onModelValueUpdate = (next: number | null) => {
  if (isPercentBugCoercion(next)) {
    modelValue.value = null
  } else {
    inputEmpty = false
    modelValue.value = next ?? null
  }
}

const { testIdAttrs } = useTestId()

const { inputClass } = useInputStyles(props)

const clearClass = computed(() => {
  return cn(
    'absolute top-1/2 -translate-y-1/2 left-auto',
    props.step ? 'right-14' : 'right-2',
  )
}) as ComputedRef<string>

const rightPaddingClass = computed(() => {
  if (props.clearable && props.step) {
    return 'pr-20'
  } else if (props.step) {
    return 'pr-14'
  } else if (props.clearable) {
    return 'pr-8'
  }
  return ''
}) as ComputedRef<string>
</script>

<template>
  <PInputWrapper v-bind="props">
    <NumberField
      v-bind="{...testIdAttrs, ...delegatedProps}"
      :model-value="modelValue"
      @update:model-value="onModelValueUpdate"
    >
      <NumberFieldContent>
        <NumberFieldDecrement
          v-if="props.step"
          class="left-auto right-6"
        />
        <NumberFieldInput 
          :data-testid="generateTestId('PNumericInput', 'input')"
          :class="cn(inputClass, rightPaddingClass, 'text-left')"
          :placeholder="props.placeholder"
          @input="onInput"
          @focus="emits('focus', $event)"
          @blur="emits('blur', $event)"
        />
        <NumberFieldIncrement v-if="props.step" />
        <PButton
          v-if="props.clearable"
          :disabled="props.disabled || props.readonly"
          type="button"
          aria-label="Clear"
          variant="neutral"
          appearance="text"
          size="small"
          icon="close-large"
          icon-button
          :class="clearClass"
          @click.stop="onClear"
        />
      </NumberFieldContent>
    </NumberField>
  </PInputWrapper>
</template>
