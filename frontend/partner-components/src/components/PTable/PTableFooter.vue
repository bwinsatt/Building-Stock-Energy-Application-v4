<script setup lang="ts">
import '@/styles/global.css'
import type { HTMLAttributes } from 'vue'
import { TableFooter } from '@/components/shadcn/ui/table'
import { useTestId } from '@/composables/useTestId'
import { cn } from '@/lib/utils'

export interface PTableFooterProps {
  class?: HTMLAttributes['class']
}

const props = defineProps<PTableFooterProps>()

const { testIdAttrs } = useTestId()
</script>

<template>
  <TableFooter
    :class="cn(
      'dark:border-(--partner-inherit-white-border)', 
      'bg-transparent [&_tr]:bg-(--partner-inherit-hovered)/25 [&_tr]:hover:bg-(--partner-inherit-hovered)/25 [&_tr]:hover:dark:bg-(--partner-inherit-hovered)/25', // Apply background to rows instead of the whole footer, remove hover from footer rows
      '[&_tr:has([data-testid*=ppagination])]:bg-transparent [&_tr:has([data-testid*=ppagination])]:hover:bg-transparent', // Pagination row should not have a background
      props.class)"
    v-bind="testIdAttrs"
  >
    <slot />
  </TableFooter>
</template>