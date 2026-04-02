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
  variant?: 'default' | 'rating'
  orientation?: 'horizontal' | 'vertical'
  class?: HTMLAttributes["class"]
}

const props = withDefaults(defineProps<PRadioGroupItemProps & RadioGroupItemProps>(), {
  disabled: false,
  size: 'medium',
  variant: 'default',
  orientation: 'horizontal',
})

const delegatedProps = reactiveOmit(props, "class", 'variant')

const forwardedProps = useForwardProps(delegatedProps)

const { testIdAttrs } = useTestId(() => {
  if (!props.name) return props.id ?? props.value ?? ''
})

const sizeClass = computed(() => {
  if (props.variant === 'rating') return ''

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
  if (props.variant === 'rating') return ''

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
    :class="cn('partner-preflight flex items-center', props.variant === 'rating' ? '' : 'gap-1', sizeClass, orientationClass)"
  >
    <template v-if="props.variant === 'rating'">
      <RadioGroupItem
        v-bind="forwardedProps"
        :class="
          cn(
            'peer flex min-w-8 select-none flex-col items-center justify-center rounded-sm border border-transparent px-2 active:bg-(--partner-primary-dark) active:text-white',
            label ? 'h-11 py-1' : 'h-8 py-0',
            'cursor-pointer bg-(--partner-fill-hovered) text-(--partner-text-primary)',
            'hover:bg-(--partner-blue-6) hover:text-white',
            'data-[state=checked]:bg-(--partner-primary-main) data-[state=checked]:text-white',
            'data-disabled:cursor-not-allowed data-disabled:text-(--partner-text-disabled) data-disabled:hover:bg-(--partner-gray-1) data-disabled:data-active:bg-(--partner-gray-6)',
            'bg-(--partner-gray-1) text-(--partner-gray-7)',
            props.class,
          )
        "
      >
        <span class="text-sm leading-none font-medium">
          <slot name="value">
            {{ value }}
          </slot>
        </span>
        <span
          v-if="label"
          class="mt-1 text-[10px] leading-none"
        >
          <slot name="label">
            {{ label }}
          </slot>
        </span>
      </RadioGroupItem>
    </template>
    <template v-else>
      <RadioGroupItem
        v-bind="forwardedProps"
        :class="
          cn(
            'peer aspect-square h-4 w-4 rounded-full border border-(--partner-action-enabled) text-primary shadow-none focus:outline-none focus-visible:ring-1 focus-visible:ring-ring',
            'cursor-pointer',
            'bg-white dark:bg-transparent',
            'data-[state=checked]:border-(--partner-primary) dark:data-[state=checked]:border-(--partner-primary) disabled:data-[state=checked]:border-(--partner-action-disabled)',
            'disabled:cursor-not-allowed disabled:opacity-50 disabled:border-(--partner-action-disabled) disabled:text-(--partner-text-disabled)',
            'hover:ring-3 hover:ring-(--partner-fill-hovered) dark:hover:ring-(--partner-fill-hovered)/20',
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
        variant="inputText"
        component="span"
        :required="required"
        :disabled="disabled"
        :class="cn('pt-0.5 text-partner-primary', !props.disabled && 'cursor-pointer')"
      >
        <slot name="label">
          {{ label }}
        </slot>
      </PLabel>
    </template>
  </div>
</template>