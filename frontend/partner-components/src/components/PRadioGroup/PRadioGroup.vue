<script setup lang="ts">
import type { RadioGroupRootEmits, RadioGroupRootProps } from "reka-ui"
import type { PRadioGroupVariants } from "."
import { RadioGroupRoot, useForwardPropsEmits } from "reka-ui"
import { computed, type HTMLAttributes } from "vue"
import { reactiveOmit } from "@vueuse/core"
import { cn } from "@/lib/utils"
import { type PRadioGroupItemProps, PRadioGroupItem } from "."
import type { Size } from '@/types/size'
import { PInputWrapper } from "@/components/PInputWrapper"
import { useTestId } from '@/composables/useTestId'

export interface PRadioGroupProps {
  name?: string
  options?: PRadioGroupItemProps[]
  variant?: PRadioGroupVariants["variant"]
  orientation?: 'horizontal' | 'vertical'
  labelOrientation?: 'horizontal' | 'vertical'
  selected?: string
  required?: boolean
  disabled?: boolean
  error?: boolean
  size?: Size
  label?: string
  helperText?: string
  errorText?: string
  class?: HTMLAttributes["class"]
}

const props = withDefaults(defineProps<PRadioGroupProps & RadioGroupRootProps>(), {
  orientation: 'horizontal',
  variant: 'default',
  required: false,
  disabled: false,
  size: 'medium',
})

const emits = defineEmits<RadioGroupRootEmits>()

const delegatedProps = reactiveOmit(props, "class")

const forwarded = useForwardPropsEmits(delegatedProps, emits)

const orientationClass = computed(() => {
  switch (props.orientation) {
    case 'horizontal':
      return 'flex-row'
    case 'vertical':
      return 'flex-col gap-0'
    default:
      return 'flex-row'
  }
})

const variantGapClass = computed(() => props.variant === 'rating' ? 'gap-2' : 'gap-4')

const { testIdAttrs } = useTestId(() => props.name ? '' : props.label)
</script>

<template>
  <PInputWrapper v-bind="props">
    <RadioGroupRoot
      :key="`PRadioGroup ${props.selected}`"
      :class="cn('flex w-fit', variantGapClass, orientationClass, props.class)"
      v-bind="{...testIdAttrs, ...forwarded}"
      :default-value="props.selected || forwarded.defaultValue"
    >
      <PRadioGroupItem 
        v-for="(option, index) in options"
        v-bind="option"
        :key="index"
        :disabled="props.disabled || option.disabled"
        :size="props.size"
        :variant="option.variant === 'rating' || props.variant === 'rating' ? 'rating' : 'default'"
        :orientation="labelOrientation || option.orientation"
      />
      <slot v-if="!options" />
    </RadioGroupRoot>
  </PInputWrapper>
</template>