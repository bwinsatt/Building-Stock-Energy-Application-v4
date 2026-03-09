<script setup lang="ts">
import '@/styles/global.css'
import type { PaginationNextProps } from "reka-ui"
import type { HTMLAttributes } from "vue"
import type { ButtonVariants } from '@/components/PButton'
import { reactiveOmit } from "@vueuse/core"
import { PIcon } from '@/components/PIcon'
import { PaginationNext, useForwardProps } from "reka-ui"
import { cn } from "@/lib/utils"
import { buttonVariants } from '@/components/PButton'

const props = withDefaults(defineProps<PaginationNextProps & {
  size?: ButtonVariants["size"]
  class?: HTMLAttributes["class"]
}>(), {
  size: "medium",
})

const delegatedProps = reactiveOmit(props, "class", "size")
const forwarded = useForwardProps(delegatedProps)
</script>

<template>
  <PaginationNext
    data-slot="pagination-next"
    :class="cn(buttonVariants({ variant: 'neutral', appearance: 'text', size, iconButton: true}),
               'gap-1 px-2.5 sm:pr-2.5',
               props.class)"
    v-bind="forwarded"
  >
    <slot>
      <span class="sr-only">Next</span>
      <PIcon name="caret-right" />
    </slot>
  </PaginationNext>
</template>
