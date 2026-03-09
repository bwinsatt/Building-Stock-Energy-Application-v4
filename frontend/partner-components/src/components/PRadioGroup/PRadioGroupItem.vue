<script setup lang="ts">
import type { RadioGroupItemProps } from "reka-ui"
import {
  RadioGroupIndicator,
  RadioGroupItem,
  useForwardProps,
} from "reka-ui"
import { computed, type HTMLAttributes } from "vue"
import { reactiveOmit } from "@vueuse/core"
import { PIcon } from "@/components/PIcon"
import { cn } from "@/lib/utils"
import type { Size } from '@/types/size'
import { useTestId } from '@/composables/useTestId'
import { PLabel } from "@/components/PLabel"

export interface PRadioGroupItemProps {
  name?: string
  id?: string
  value?: string
  label?: string
  disabled?: boolean
  required?: boolean
  size?: Size
  orientation?: 'horizontal' | 'vertical'
  class?: HTMLAttributes["class"]
}

const props = withDefaults(defineProps<PRadioGroupItemProps & RadioGroupItemProps>(), {
  disabled: false,
  size: 'medium',
  orientation: 'horizontal',
})

const delegatedProps = reactiveOmit(props, "class")

const forwardedProps = useForwardProps(delegatedProps)

const { testIdAttrs } = useTestId(() => {
  if (!props.name) return props.id ?? props.value ?? ''
})

const sizeClass = computed(() => {
  switch (props.size) {
    case 'small':
      return 'py-1'
    case 'large':
      return 'py-3'
    default:
      return 'py-2'
  }
})

const orientationClass = computed(() => {
  switch (props.orientation) {
    case 'horizontal':
      return 'flex-row'
    case 'vertical':
      return 'flex-col'
    default:
      return 'flex-row'
  }
})
</script>

<template>
  <div
    v-bind="testIdAttrs"
    :class="cn('flex items-center gap-1', sizeClass, orientationClass)"
  >
    <RadioGroupItem
      v-bind="forwardedProps"
      :class="
        cn(
          'peer aspect-square h-4 w-4 rounded-full border border-(--partner-action-enabled) text-primary shadow-none focus:outline-none focus-visible:ring-1 focus-visible:ring-ring',
          'cursor-pointer',
          'bg-white dark:bg-transparent',
          'dark:border-(--partner-action-enabled)/50',
          'data-[state=checked]:border-(--partner-primary) dark:data-[state=checked]:border-(--partner-primary) disabled:data-[state=checked]:border-(--partner-action-disabled)',
          'disabled:cursor-not-allowed disabled:opacity-50 disabled:border-(--partner-action-disabled) disabled:text-(--partner-text-disabled)',
          'hover:ring-3 hover:ring-(--partner-fill-hover) dark:hover:ring-(--partner-fill-hover)/20',
          props.class,
        )
      "
    >
      <RadioGroupIndicator class="flex items-center justify-center">
        <PIcon
          name="dot-custom"
          size="6px"
          :class="cn('text-(--partner-primary) sibling:disabled:var(--partner-text-disabled)')"
        />
      </RadioGroupIndicator>
    </RadioGroupItem>
    <PLabel
      v-if="label"
      :for="id"
      :required="required"
      :disabled="disabled"
      :class="cn('cursor-pointer dark:text-(--partner-text-white)')"
    >
      <slot name="label">
        {{ label }}
      </slot>
    </PLabel>
  </div>
</template>
