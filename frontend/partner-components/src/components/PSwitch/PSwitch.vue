<script setup lang="ts">
import '@/styles/global.css'
import type { HTMLAttributes, ComputedRef } from "vue"
import { computed } from "vue"
import {
  SwitchRoot,
  SwitchThumb,
  useForwardPropsEmits,
  type SwitchRootProps,
} from "reka-ui"
import { reactiveOmit } from "@vueuse/core"
import { cn } from "@/lib/utils"
import { useTestId } from "@/composables/useTestId"
import { PLabel } from "@/components/PLabel"
import type { Size } from "@/types/size"

export interface PSwitchProps {
  class?: HTMLAttributes["class"]
  modelValue?: boolean
  defaultValue?: boolean
  disabled?: boolean
  label?: string
  id?: string
  size?: Size
}

const props = withDefaults(defineProps<PSwitchProps & SwitchRootProps>(), {
  size: 'medium',
})

export interface PSwitchEmits {
  (e: 'update:modelValue', value: boolean): void
}

const emits = defineEmits<PSwitchEmits>()

const delegatedProps = reactiveOmit(props, "class")

const forwarded = useForwardPropsEmits(delegatedProps, emits)

const { testIdAttrs } = useTestId()

const sizeClassRoot = computed(() => {
  switch (props.size) {
    case 'small':
      return 'h-4 w-7'
    case 'large':
      return 'h-6 w-11'
    default:
      return 'h-5 w-9'
  }
}) as ComputedRef<string>

const sizeClassThumb = computed(() => {
  switch (props.size) {
    case 'small':
      return 'h-3 w-3 data-[state=checked]:translate-x-3'
    case 'large':
      return 'h-5 w-5 data-[state=checked]:translate-x-5'
    default:
      return 'h-4 w-4 data-[state=checked]:translate-x-4'
  }
}) as ComputedRef<string>
</script>

<template>
  <div
    v-bind="testIdAttrs"
    :class="cn('partner-preflight flex flex-row gap-1 items-center justify-start', props.class)"
  >
    <SwitchRoot
      v-bind="forwarded"
      :class="cn(
        'peer inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent shadow-none transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background',
        'disabled:cursor-not-allowed',
        'data-[state=checked]:bg-primary data-[state=unchecked]:bg-input',
        'disabled:data-[state=checked]:bg-(--partner-inherit-disabled) disabled:data-[state=unchecked]:bg-(--partner-inherit-disabled)',
        sizeClassRoot,
        props.class,
      )"
    >
      <SwitchThumb
        :class="cn(
          'pointer-events-none block h-4 w-4 rounded-full bg-background shadow-none ring-0 transition-transform data-[state=checked]:translate-x-4 data-[state=unchecked]:translate-x-0',
          sizeClassThumb,
        )"
      >
        <slot name="thumb" />
      </SwitchThumb>
    </SwitchRoot>
    <PLabel
      v-if="props.label"
      :for="props.id"
      :disabled="props.disabled"
    >
      <slot name="label">
        {{ props.label }}
      </slot>
    </PLabel>
  </div>
</template>