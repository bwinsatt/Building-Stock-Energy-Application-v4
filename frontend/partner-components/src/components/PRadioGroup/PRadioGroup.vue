<script setup lang="ts">
import type { RadioGroupRootEmits, RadioGroupRootProps } from "reka-ui"
import { RadioGroupRoot, useForwardPropsEmits } from "reka-ui"
import { computed, type HTMLAttributes } from "vue"
import { reactiveOmit } from "@vueuse/core"
import { cn } from "@/lib/utils"
import { type PRadioGroupItemProps, PRadioGroupItem } from "."
import type { Size } from '@/types/size'
import { PLabel } from "@/components/PLabel"
import { useInputStyles } from "@/composables/useInputStyles"
import { useTestId } from '@/composables/useTestId'

export interface PRadioGroupProps {
  name?: string
  options?: PRadioGroupItemProps[]
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

const { helperErrorText } = useInputStyles(props)

const { testIdAttrs } = useTestId(() => props.name ? '' : props.label)
</script>

<template>
  <div
    v-bind="testIdAttrs"
    class="flex flex-col gap-1"
  >
    <PLabel
      v-if="label"
      :disabled="disabled"
      :required="required"
      :error="error"
    >
      <slot name="label">
        {{ label }}
      </slot>
    </PLabel>
    <RadioGroupRoot
      :class="cn('flex w-fit gap-4', orientationClass, props.class)"
      v-bind="forwarded"
      :default-value="props.selected || forwarded.defaultValue"
    >
      <PRadioGroupItem 
        v-for="(option, index) in options"
        v-bind="option"
        :key="index"
        :size="props.size"
        :orientation="labelOrientation || option.orientation"
      />
      <slot v-if="!options" />
    </RadioGroupRoot>
    <PLabel
      v-if="helperErrorText"
      :disabled="disabled"
      :error="error"
    >
      {{ helperErrorText }}
    </PLabel>
  </div>
</template>
