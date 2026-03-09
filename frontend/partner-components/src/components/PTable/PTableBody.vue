<script setup lang="ts">
import '@/styles/global.css'
import type { HTMLAttributes } from 'vue'
import { TableBody } from '@/components/shadcn/ui/table'
import { useTestId } from '@/composables/useTestId'
import { cn } from '@/lib/utils'

export interface PTableBodyProps {
  class?: HTMLAttributes['class']
}

const props = defineProps<PTableBodyProps>()

const { testIdAttrs } = useTestId()
</script>

<template>
  <TableBody
    :class="cn('', props.class)"
    v-bind="testIdAttrs"
  >
    <slot />
  </TableBody>
</template>
