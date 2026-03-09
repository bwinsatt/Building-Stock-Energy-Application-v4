<script setup lang="ts">
import '@/styles/global.css'
import type { HTMLAttributes, ComputedRef } from 'vue'
import { computed, provide, ref } from 'vue'
import { TableHeader } from '@/components/shadcn/ui/table'
import { useTestId } from '@/composables/useTestId'
import { cn } from '@/lib/utils'
import type { Size } from '@/types/size'

export interface PTableHeaderProps {
  class?: HTMLAttributes['class']
  variant?: 'gray-fill' | 'blue-border'
  size?: Size
  singleSort?: boolean
}

const props = withDefaults(defineProps<PTableHeaderProps>(), {
  variant: 'blue-border',
  size: 'medium',
})

const variantClass = computed(() => {
  if (props.variant === 'gray-fill') {
    return 'bg-(--partner-background-gray) dark:bg-(--partner-gray-7) border-t border-b border-(--partner-border-disabled) dark:border-(--partner-inherit-white-border)'
  }
  if (props.variant === 'blue-border') {
    return 'bg-transparent border-t-2 border-b-2 border-(--partner-primary)'
  }
  return ''
}) as ComputedRef<string>

provide('headerSize', computed(() => props.size))

const { testIdAttrs } = useTestId()

const sortableHeads = ref<Set<() => void>>(new Set())

const registerSortReset = (resetFn: () => void) => {
  sortableHeads.value.add(resetFn)
  return () => sortableHeads.value.delete(resetFn) // cleanup on unmount
}

const resetOtherSorts = (except: () => void) => {
  sortableHeads.value.forEach((resetFn) => {
    if (resetFn !== except) resetFn()
  })
}

provide('registerSortReset', props.singleSort ? registerSortReset : undefined)
provide('resetOtherSorts', props.singleSort ? resetOtherSorts : undefined)
</script>

<template>
  <TableHeader
    :class="cn(variantClass, props.class)"
    v-bind="testIdAttrs"
  >
    <slot />
  </TableHeader>
</template>