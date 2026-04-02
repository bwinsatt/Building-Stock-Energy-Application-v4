<script setup lang="ts">
import '@/styles/global.css'
import type { HTMLAttributes } from 'vue'
import { cn } from '@/lib/utils'
import { reactiveOmit } from '@vueuse/core'
import { default as PTableRow } from './PTableRow.vue'
import { default as PTableCell } from './PTableCell.vue'
import { useTestId } from '@/composables/useTestId'

export interface PTableEmptyProps {
  class?: HTMLAttributes['class']
  colspan?: number
}

const props = withDefaults(defineProps<PTableEmptyProps>(), {
  colspan: 999,
})

const { testIdAttrs } = useTestId()

const delegatedProps = reactiveOmit(props, "class")
</script>

<template>
  <PTableRow>
    <PTableCell
      :class="
        cn(
          'partner-preflight',
          'p-4 whitespace-nowrap align-middle text-sm text-foreground',
          props.class,
        )
      "
      v-bind="{ ...delegatedProps, ...testIdAttrs }"
    >
      <div class="flex items-center justify-center gap-1 py-10">
        <slot />
      </div>
    </PTableCell>
  </PTableRow>
</template>
=