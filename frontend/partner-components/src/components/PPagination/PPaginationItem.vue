<script setup lang="ts">
import '@/styles/global.css'
import type { PaginationListItemProps } from "reka-ui"
import type { HTMLAttributes } from "vue"
import type { ButtonVariants } from '@/components/PButton'
import { reactiveOmit } from "@vueuse/core"
import { PaginationListItem } from "reka-ui"
import { cn } from "@/lib/utils"
import { buttonVariants } from '@/components/PButton'
import { PTypography } from '@/components/PTypography'

const props = withDefaults(defineProps<PaginationListItemProps & {
  size?: ButtonVariants["size"]
  class?: HTMLAttributes["class"]
  isActive?: boolean
}>(), {
  size: "medium",
})

const delegatedProps = reactiveOmit(props, "class", "size", "isActive")

const activeClass = (isActive: boolean) => {
  return cn((isActive ? `absolute bottom-0 w-4 h-1 bg-partner-primary` : ''))
}
</script>

<template>
  <PaginationListItem
    data-slot="pagination-item"
    v-bind="delegatedProps"
    :class="cn(
      'relative flex items-center justify-center',
      buttonVariants({
        variant: 'neutral',
        appearance: 'text',
        size,
      }),
      props.class)"
  >
    <PTypography
      variant="body2"
    >
      <slot />
    </PTypography>
    <div
      v-if="isActive"
      :class="cn(activeClass(isActive))"
    />
  </PaginationListItem>
</template>
