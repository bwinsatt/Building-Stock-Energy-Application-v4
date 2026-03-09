<script setup lang="ts">
import { computed, type HTMLAttributes } from "vue"
import { useVModel } from "@vueuse/core"
import { cn } from "@/lib/utils"
import { useTestId } from "@/composables/useTestId"
import type { Size } from "@/types/size"
import { PLabel } from "@/components/PLabel"
import { useInputStyles } from "@/composables/useInputStyles"

export interface PTextAreaProps {
  class?: HTMLAttributes["class"]
  defaultValue?: string | number
  modelValue?: string | number
  maxLength?: number
  minLines?: number
  resize?: boolean
  size?: Size
  placeholder?: string
  error?: boolean
  disabled?: boolean
  required?: boolean
  label?: string
  id?: string
  helperText?: string
  errorText?: string
}

const props = defineProps<PTextAreaProps>()

export interface PTextAreaEmits {
  (e: "update:modelValue", payload: string | number): void
}

const emits = defineEmits<PTextAreaEmits>()

const modelValue = useVModel(props, "modelValue", emits, {
  passive: true,
  defaultValue: props.defaultValue,
})

const { testIdAttrs } = useTestId()

const { helperErrorText, sizeClass: inputSizeClass, disabledClass, errorClass } = useInputStyles(props)

const resizeClass = computed(() => {
  return !props.resize ? 'resize-none' : ''
})

const fixedHeightClass = computed(() => {
  return props.minLines ? `field-sizing-fixed` : 'field-sizing-content'
})

const sizeClass = computed(() => {
  return inputSizeClass.value.replace('h-', 'min-h-')
})
</script>

<template>
  <div class="flex flex-col gap-1 w-full">
    <div class="flex flex-row justify-between gap-1 w-full">
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
      <PLabel
        v-if="props.maxLength"
        :for="props.id"
        :disabled="props.disabled"
        :error="props.error"
      >
        <slot name="maxLength">
          {{ (modelValue as string)?.length }}/{{ props.maxLength }}
        </slot>
      </PLabel>
    </div>
    <textarea 
      v-bind="{...testIdAttrs, ...$attrs}" 
      :id="props.id" 
      v-model="modelValue" 
      :maxlength="props.maxLength"
      :class="cn('flex w-full rounded-sm border border-input bg-transparent px-3 py-1.5 partner-inputText transition-colors',
                 resizeClass,
                 sizeClass,
                 fixedHeightClass,
                 'placeholder:text-(--partner-text-placeholder)',
                 'hover:border-(--partner-border-hovered) focus-visible:border-(--partner-border-active)',
                 'focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-(--partner-border-active)',
                 errorClass,
                 disabledClass,
                 'disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:border-(--partner-border-disabled)',
                 props.class)"
      :placeholder="props.placeholder"
      :disabled="props.disabled"
      :rows="props.minLines"
    />
    <PLabel
      v-if="helperErrorText"
      :disabled="props.disabled" 
      :error="props.error"
    >
      {{ helperErrorText }}
    </PLabel>
  </div>
</template>
