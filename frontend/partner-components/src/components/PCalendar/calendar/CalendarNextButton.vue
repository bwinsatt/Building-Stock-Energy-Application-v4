<script lang="ts" setup>
import type { CalendarNextProps } from "reka-ui"
import type { HTMLAttributes } from "vue"
import { reactiveOmit } from "@vueuse/core"
import { PIcon } from '@/components/PIcon'
import { CalendarNext, useForwardProps } from "reka-ui"
import { cn } from "@/lib/utils"
import { buttonVariants } from '@/components/PButton'

const props = defineProps<CalendarNextProps & { class?: HTMLAttributes["class"] }>()

const delegatedProps = reactiveOmit(props, "class")

const forwardedProps = useForwardProps(delegatedProps)
</script>

<template>
  <CalendarNext
    :class="cn(
      buttonVariants({ variant: 'neutral', appearance: 'text' }),
      'h-7 w-7 bg-transparent p-0',
      props.class,
    )"
    v-bind="forwardedProps"
  >
    <slot>
      <PIcon
        name="chevron-right"
        size="small"
      />
    </slot>
  </CalendarNext>
</template>
