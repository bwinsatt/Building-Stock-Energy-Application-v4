<script setup lang="ts">
import '@/styles/global.css'
import { ref, computed, type HTMLAttributes, type ComputedRef } from "vue"
import { useVModel } from "@vueuse/core"
import { cn } from "@/lib/utils"
import { useTestId } from "@/composables/useTestId"
import { PIcon } from "@/components/PIcon"
import { PButton } from "@/components/PButton"
import type { Size } from "@/types/size"

export interface PSearchBarProps {
  class?: HTMLAttributes["class"]
  modelValue?: string | number
  defaultValue?: string | number
  placeholder?: string
  disabled?: boolean
  size?: Size
}

const props = defineProps<PSearchBarProps>()

export interface PSearchBarEmits {
  (e: "update:modelValue", payload: string | number): void
  (e: "search", payload: string | number): void
}

const emits = defineEmits<PSearchBarEmits>()

const modelValue = useVModel(props, "modelValue", emits, {
  passive: true,
  defaultValue: props.defaultValue,
})

const { testId, testIdAttrs } = useTestId()

const sizeClass = computed(() => {
  switch (props.size) {
    case 'small':
      return 'h-7'
    case 'large':
      return 'h-10'
    case 'medium':
    default:
      return 'h-8'
  }
})

const buttonSize = computed(() => {
  switch (props.size) {
    case 'large':
      return 'medium'
    default:
      return 'small'
  }
}) as ComputedRef<Size>

const input = ref<HTMLInputElement | null>(null)

const focusInput = () => {
  input.value?.focus()
}

const clearInput = () => {
  modelValue.value = ''
  emits('update:modelValue', modelValue.value as string)
}

const handleSearch = () => {
  emits('search', modelValue.value as string)
}
</script>

<template>
  <div
    v-bind="{...testIdAttrs, ...$attrs}"
    :class="cn('flex flex-row gap-2 items-center align-middle p-1', 
               sizeClass,
               'border-b border-(--partner-border-default)',
               'hover:border-(--partner-border-hovered)',
               'focus-within:border-(--partner-border-active)',
               'focus-within:outline-none focus-within:shadow-[0_1px_0_0_var(--partner-border-active)]',
               'data-[disabled=true]:text-(--partner-text-disabled) data-[disabled=true]:border-(--partner-border-disabled)',
               'data-[disabled=true]:bg-(--partner-fill-disabled)',
               'data-[disabled=true]:cursor-not-allowed dark:data-[disabled=true]:opacity-50 data-[disabled=true]:hover:border-(--partner-border-disabled)',
               props.class)"
    :data-disabled="props.disabled"
  >
    <PIcon
      name="search"
      size="small"
      @click.stop="focusInput"
    />
    <input 
      ref="input"
      v-model="modelValue"
      :data-testid="`${testId}-input`"
      type="text"
      :placeholder="props.placeholder"
      :disabled="props.disabled"
      :class="cn('flex w-full',
                 'placeholder:text-(--partner-text-placeholder)',
                 'focus:outline-none focus:ring-0',
                 'disabled:cursor-not-allowed',
                 props.class)"
      @keyup.enter.stop="handleSearch"
    >
    <PButton
      v-if="modelValue"
      name="clear"
      variant="neutral"
      appearance="text"
      icon="close"
      icon-button
      :size="buttonSize"
      :disabled="props.disabled"
      @click.stop="clearInput"
    />
    <PButton
      name="search"
      variant="primary"
      appearance="contained"
      icon="arrow-right"
      icon-button
      :size="buttonSize"
      :disabled="props.disabled"
      @click.stop="handleSearch"
    />
  </div>
</template>