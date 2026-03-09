<script setup lang="ts">
import '@/styles/global.css'
import type { HTMLAttributes } from 'vue'
import { Table } from '@/components/shadcn/ui/table'
import { useTestId } from '@/composables/useTestId'
import { cn } from '@/lib/utils'

export interface PTableProps {
  class?: HTMLAttributes['class']
}

const props = defineProps<PTableProps>()

const { testIdAttrs } = useTestId()
</script>

<template>
  <Table
    :class="cn('', props.class)"
    v-bind="testIdAttrs"
  >
    <slot />
  </Table>
</template>