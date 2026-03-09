<script setup lang="ts">
import '@/styles/global.css'
import { type HTMLAttributes } from "vue"
import { useVModel } from "@vueuse/core"
import { useTestId } from "@/composables/useTestId"
import type { Size } from "@/types/size"
import { PLabel } from "@/components/PLabel"
import { useInputStyles } from "@/composables/useInputStyles"

export interface PTextInputProps {
  defaultValue?: string | number
  modelValue?: string | number
  class?: HTMLAttributes["class"]
  size?: Size
  placeholder?: string
  error?: boolean
  disabled?: boolean
  required?: boolean
  label?: string
  id?: string
  type?: 'text' | 'email' | 'password' | 'tel' | 'url'
  helperText?: string
  errorText?: string
}

const props = withDefaults(defineProps<PTextInputProps>(), {
  type: 'text',
})

export interface PTextInputEmits {
  (e: "update:modelValue", payload: string | number): void
}

const emits = defineEmits<PTextInputEmits>()

const modelValue = useVModel(props, "modelValue", emits, {
  passive: true,
  defaultValue: props.defaultValue,
})

const { testIdAttrs } = useTestId()

const { helperErrorText, inputClass } = useInputStyles(props)
</script>

<template>
  <div class="flex flex-col gap-1">
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
    <input 
      v-bind="{...testIdAttrs, ...$attrs}" 
      :id="props.id"
      v-model="modelValue"
      :class="inputClass"
      :placeholder="props.placeholder"
      :disabled="props.disabled"
      :type="props.type"
    >
    <PLabel
      v-if="helperErrorText"
      :disabled="props.disabled" 
      :error="props.error"
    >
      {{ helperErrorText }}
    </PLabel>
  </div>
</template>
