<script setup lang="ts">
import '@/styles/global.css'
import type { HTMLAttributes, ComputedRef } from 'vue'
import { computed } from 'vue'
import { TableCaption } from '@/components/shadcn/ui/table'
import { useTestId } from '@/composables/useTestId'
import { cn } from '@/lib/utils'

export interface PTableCaptionProps {
  class?: HTMLAttributes['class']
  location?: 'top' | 'bottom'
}

const props = withDefaults(defineProps<PTableCaptionProps>(), {
  location: 'bottom',
})

const locationClass = computed(() => {
  return props.location === 'top' ? 'caption-top mb-4 mt-0' : 'caption-bottom mb-0 mt-4'
}) as ComputedRef<string>

const { testIdAttrs } = useTestId()
</script>

<template>
  <TableCaption
    :class="cn(locationClass, props.class)"
    v-bind="testIdAttrs"
  >
    <slot />
  </TableCaption>
</template>