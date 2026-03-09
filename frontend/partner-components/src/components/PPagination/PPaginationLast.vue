<script setup lang="ts">
import '@/styles/global.css'
import type { PaginationLastProps } from "reka-ui"
import type { HTMLAttributes } from "vue"
import type { ButtonVariants } from '@/components/PButton'
import { reactiveOmit } from "@vueuse/core"
import { PIcon } from '@/components/PIcon'
import { PaginationLast, useForwardProps } from "reka-ui"
import { cn } from "@/lib/utils"
import { buttonVariants } from '@/components/PButton'

const props = withDefaults(defineProps<PaginationLastProps & {
  size?: ButtonVariants["size"]
  class?: HTMLAttributes["class"]
}>(), {
  size: "medium",
})

const delegatedProps = reactiveOmit(props, "class", "size")
const forwarded = useForwardProps(delegatedProps)
</script>

<template>
  <PaginationLast
    data-slot="pagination-last"
    :class="cn(buttonVariants({ variant: 'neutral', appearance: 'text', size, iconButton: true}),
               'gap-1 px-2.5 sm:pr-2.5',
               props.class)"
    v-bind="forwarded"
  >
    <slot>
      <span class="sr-only">Last</span>
      <PIcon name="page-last" />
    </slot>
  </PaginationLast>
</template>
