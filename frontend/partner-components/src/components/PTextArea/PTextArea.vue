<script setup lang="ts">
import { computed, type HTMLAttributes } from "vue"
import { useVModel } from "@vueuse/core"
import { cn } from "@/lib/utils"
import { useTestId } from "@/composables/useTestId"
import type { Size } from "@/types/size"
import { PLabel } from "@/components/PLabel"
import { PInputWrapper } from "@/components/PInputWrapper"
import { useInputStyles } from "@/composables/useInputStyles"

defineOptions({ inheritAttrs: false })

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

const { inputClass: inputClassStyles, sizeClass } = useInputStyles(props)

const resizeClass = computed(() => {
  return !props.resize ? 'resize-none' : ''
})

const fixedHeightClass = computed(() => {
  return props.minLines ? `field-sizing-fixed` : 'field-sizing-content'
})

const inputClass = computed(() => {
  return inputClassStyles.value.replace(sizeClass.value, sizeClass.value.replace('h-', 'min-h-'))
})
</script>

<template>
  <PInputWrapper v-bind="props">
    <template #label-right>
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
    </template>
    <textarea 
      v-bind="{...testIdAttrs, ...$attrs}" 
      :id="props.id" 
      v-model="modelValue" 
      :maxlength="props.maxLength"
      :class="cn('partner-scrollbar',
                 inputClass,
                 resizeClass,
                 fixedHeightClass,
                 props.class)"
      :placeholder="props.placeholder"
      :disabled="props.disabled"
      :rows="props.minLines"
    />
  </PInputWrapper>
</template>
