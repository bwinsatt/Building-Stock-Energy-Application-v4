<script setup lang="ts">
import type { DropdownMenuItemProps } from "reka-ui"
import type { HTMLAttributes } from "vue"
import { reactiveOmit } from "@vueuse/core"
import { DropdownMenuItem, useForwardProps } from "reka-ui"
import { cn } from "@/lib/utils"
import { PTypography } from "@/components/PTypography"

const props = defineProps<DropdownMenuItemProps & { class?: HTMLAttributes["class"], inset?: boolean, description?: string }>()

const delegatedProps = reactiveOmit(props, "class")

const forwardedProps = useForwardProps(delegatedProps)
</script>

<template>
  <DropdownMenuItem
    v-bind="forwardedProps"
    :class="cn(
      'relative flex cursor-default select-none items-center rounded-sm gap-2 px-2 py-1.5 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50 [&>svg]:size-4 [&>svg]:shrink-0',
      inset && 'pl-8',
      props.class,
    )"
  >
    <div class="flex flex-col gap-0 w-full">
      <slot />
      <PTypography
        v-if="description || $slots.description"
        variant="body2"
        truncate
        :class="cn('text-sm text-(--partner-text-secondary)')"
      >
        <slot name="description">
          {{ description }}
        </slot>
      </PTypography>
    </div>
  </DropdownMenuItem>
</template>
