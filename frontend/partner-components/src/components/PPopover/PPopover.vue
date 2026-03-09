<script setup lang="ts">
import '@/styles/global.css'
import { computed, type HTMLAttributes, type ComputedRef } from 'vue'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/shadcn/ui/popover'
import { PopoverArrow, PopoverClose } from 'reka-ui'
import { useTestId } from '@/composables/useTestId'
import { PButton } from '@/components/PButton'
import { cn } from '@/lib/utils'

export type PopoverDirections = 'none' | 'top' | 'bottom' | 'left' | 'right'

export interface PPopoverProps {
  class?: HTMLAttributes['class'],
  defaultOpen?: boolean,
  open?: boolean,
  direction?: PopoverDirections,
  showArrow?: boolean,
  showClose?: boolean,
  offset?: number,
  openDuration?: number, // The duration in milliseconds for the popover to open
  closeDuration?: number, // The duration in milliseconds for the popover to close
}

export interface PPopoverEmits {
  (e: 'update:open', value: boolean): void,
}

const props = withDefaults(defineProps<PPopoverProps>(), {
  defaultOpen: false,
  open: undefined,
  direction: 'bottom',
  offset: 6,
  openDuration: 400,
  closeDuration: 100,
})

const emits = defineEmits<PPopoverEmits>()

const { testIdAttrs } = useTestId()

type PopoverSide = 'top' | 'bottom' | 'left' | 'right' | undefined
const direction = computed(() => {
  if (props.direction === 'none') return undefined
  return props.direction as PopoverSide
}) as ComputedRef<PopoverSide>
</script>

<template>
  <Popover
    :default-open="props.defaultOpen"
    :open="props.open"
    @update:open="emits('update:open', $event)"
  >
    <PopoverTrigger as-child>
      <slot name="trigger" />
    </PopoverTrigger>
    <PopoverContent
      v-bind="testIdAttrs"
      :side="direction || 'bottom'"
      :side-offset="props.offset"
      :style="{
        '--popover-open-duration': `${props.openDuration}ms`,
        '--popover-close-duration': `${props.closeDuration}ms`,
      }"
      :class="cn('p-2 border-none shadow-md rounded-md bg-(--partner-background-popover)', 
                 `data-[state=open]:duration-(--popover-open-duration) data-[state=closed]:duration-(--popover-close-duration)`,
                 props.class)"
    >
      <PopoverClose
        v-if="props.showClose"
        as-child
        :class="cn('absolute top-2 right-2')"
      >
        <slot name="close">
          <PButton
            name="close"
            variant="neutral"
            appearance="text"
            icon="close"
            :icon-button="true"
          />
        </slot>
      </PopoverClose>
      <PopoverArrow 
        v-if="props.showArrow"
        :width="10"
        :height="5"
        class="fill-(--partner-background-popover) drop-shadow-md"
      />
      <slot name="content" />
    </PopoverContent>
  </Popover>
</template>