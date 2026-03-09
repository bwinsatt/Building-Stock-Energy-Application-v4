<script setup lang="ts">
import '@/styles/global.css'
import type { HTMLAttributes, ComputedRef } from 'vue'
import { computed } from 'vue'
import { cn } from '@/lib/utils'
import { useTestId } from '@/composables/useTestId'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/shadcn/ui/tooltip'
import { TooltipArrow } from 'reka-ui'

export type TooltipDirections = 'none' | 'top' | 'bottom' | 'left' | 'right'

export interface PTooltipProps {
  class?: HTMLAttributes['class'],
  disabled?: boolean,
  defaultOpen?: boolean, // The open state of the tooltip when it is initially rendered. Use when you do not need to control its open state.
  open?: boolean, // Controlled open state of the tooltip
  disableClosingTrigger?: boolean, // Whether the tooltip should not be closed when the trigger is clicked
  direction?: TooltipDirections, // The direction or side of the tooltip in relation to the trigger
  offset?: number,
  delayDuration?: number // The delay duration in milliseconds before the tooltip is opened
  skipDelayDuration?: number // How much time a user has to enter another trigger without incurring a delay again.
  closeDuration?: number // The duration in milliseconds for the tooltip to close
}

const props = withDefaults(defineProps<PTooltipProps>(), {
  defaultOpen: false,
  open: undefined,
  direction: 'bottom',
  offset: 2,
  delayDuration: 400,
  closeDuration: 100,
})

export interface PTooltipEmits {
  (e:'update:open', value: boolean): void,
}

const emits = defineEmits<PTooltipEmits>()

const { testIdAttrs } = useTestId()

type TooltipSide = 'top' | 'bottom' | 'left' | 'right' | undefined
const direction = computed(() => {
  if (props.direction === 'none') return undefined
  return props.direction as TooltipSide
}) as ComputedRef<TooltipSide>
</script>

<template>
  <TooltipProvider 
    v-bind="testIdAttrs"
    :disabled="props.disabled"
    :delay-duration="props.delayDuration"
    :skip-delay-duration="props.skipDelayDuration"
    :disable-closing-trigger="props.disableClosingTrigger"
  >
    <Tooltip 
      :default-open="props.defaultOpen"
      :open="props.open"
      @update:open="emits('update:open', $event)"
    >
      <TooltipTrigger as-child>
        <slot name="tooltip-trigger" />
      </TooltipTrigger>
      <TooltipContent
        :style="{ '--tooltip-close-duration': `${props.closeDuration}ms` }"
        :class="cn('z-999 relative size-fit max-w-70 overflow-visible rounded-sm bg-(--partner-fill-tooltip) partner-tooltip text-partner-white px-2 py-1', 
                   `data-[state=closed]:duration-(--tooltip-close-duration)`,
                   props.class)"
        :side="direction || 'bottom'"
        :side-offset="props.offset + 4"
      >
        <TooltipArrow
          v-if="direction"
          :width="8"
          :height="4"
          class="fill-(--partner-fill-tooltip)"
        />
        <slot name="tooltip-content" />
      </TooltipContent>
    </Tooltip>
  </TooltipProvider>
</template>