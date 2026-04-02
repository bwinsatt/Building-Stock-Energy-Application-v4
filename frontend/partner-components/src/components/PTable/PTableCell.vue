<script setup lang="ts">
import '@/styles/global.css'
import type { HTMLAttributes, ComputedRef } from 'vue'
import { computed, getCurrentInstance, provide } from 'vue'
import { TableCell } from '@/components/shadcn/ui/table'
import { useTestId } from '@/composables/useTestId'
import { cn } from '@/lib/utils'

export interface PTableCellProps {
  class?: HTMLAttributes['class']
  truncate?: boolean
}

export interface PTableCellEmits {
  (e: 'click', event: MouseEvent): void
}

const props = defineProps<PTableCellProps>()

const emits = defineEmits<PTableCellEmits>()

// Provide truncate to descendants
provide('truncate', props.truncate)

// Apply styles to correct rendering of other components within this cell.
const componentSpecificClasses = computed(() => {
  return [
    '[&_[data-testid*=pcheckbox]]:!py-0',
  ].join(' ')
}) as ComputedRef<string>

const instance = getCurrentInstance()
const hasClickListener = computed(() => instance?.vnode.props?.onClick !== undefined) as ComputedRef<boolean>

const clickableClass = computed(() => {
  return hasClickListener.value ? 'cursor-pointer hover:bg-(--partner-inherit-hovered)' : ''
}) as ComputedRef<string>

const truncateClass = computed(() => {
  return props.truncate ? 'truncate' : 'text-wrap'
}) as ComputedRef<string>

const { testIdAttrs } = useTestId()
</script>

<template>
  <TableCell
    :class="cn('partner-preflight p-3 partner-body1', componentSpecificClasses, clickableClass, truncateClass, props.class)"
    v-bind="testIdAttrs"
    @click.stop="emits('click', $event)"
  >
    <slot />
  </TableCell>
</template>