<script setup lang="ts">
import '@/styles/global.css'
import type { HTMLAttributes } from 'vue'
import { TableRow } from '@/components/shadcn/ui/table'
import { useTestId } from '@/composables/useTestId'
import { cn } from '@/lib/utils'

export interface PTableRowProps {
  class?: HTMLAttributes['class']
}

const props = defineProps<PTableRowProps>()

const { testIdAttrs } = useTestId()
</script>

<template>
  <TableRow
    :class="cn(
      'partner-preflight',
      'hover:bg-(--partner-fill-hovered)',
      '[&:has(th)]:border-b-0 [&:has(th)]:hover:bg-transparent [&:has(th)]:hover:dark:bg-transparent', // Header row specifics
      props.class,
    )"
    v-bind="testIdAttrs"
  >
    <slot />
  </TableRow>
</template>