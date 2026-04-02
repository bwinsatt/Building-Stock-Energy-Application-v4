<script setup lang="ts">
import '@/styles/global.css'
import { type HTMLAttributes, computed, type ComputedRef } from "vue"
import { useVModel } from "@vueuse/core"
import { useTestId } from "@/composables/useTestId"
import type { Size } from "@/types/size"
import { useInputStyles } from "@/composables/useInputStyles"
import { PInputWrapper } from "@/components/PInputWrapper"
import { PIcon, type PIconProps } from "@/components/PIcon"
import { cn } from "@/lib/utils"
import { PButton } from "@/components/PButton"

defineOptions({ inheritAttrs: false })

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
  iconLeft?: PIconProps
  iconRight?: PIconProps
  clearable?: boolean
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

const { inputClass } = useInputStyles(props)

const iconProps = computed(() => {
  return {
    size: 'small',
  }
}) as ComputedRef<PIconProps>

const rightIconClass = computed(() => {
  return cn(
    'absolute pointer-events-none',
    props.clearable ? 'right-8' : 'right-3',
  )
}) as ComputedRef<string>

const rightPaddingClass = computed(() => {
  if (props.iconRight && props.clearable) {
    return 'pr-13'
  } else if (props.iconRight || props.clearable) {
    return 'pr-8'
  }
  return ''
}) as ComputedRef<string>

const onClear = () => {
  modelValue.value = ''
}
</script>

<template>
  <PInputWrapper v-bind="props">
    <div class="relative flex items-center">
      <PIcon
        v-if="props.iconLeft"
        v-bind="{...iconProps, ...props.iconLeft}"
        class="absolute left-3 pointer-events-none"
      />
      <input
        v-bind="{...testIdAttrs, ...$attrs}"
        :id="props.id"
        v-model="modelValue"
        :class="cn(inputClass, props.iconLeft && 'pl-8', rightPaddingClass)"
        :placeholder="props.placeholder"
        :disabled="props.disabled"
        :type="props.type"
      >
      <PIcon
        v-if="props.iconRight"
        v-bind="{...iconProps, ...props.iconRight}"
        :class="cn(rightIconClass, props.iconRight?.class)"
      />
      <PButton
        v-if="props.clearable"
        :disabled="props.disabled"
        type="button"
        aria-label="Clear"
        variant="neutral"
        appearance="text"
        size="small"
        icon="close-large"
        icon-button
        class="absolute right-2 cursor-pointer"
        @click.stop="onClear"
      />
    </div>
  </PInputWrapper>
</template>
