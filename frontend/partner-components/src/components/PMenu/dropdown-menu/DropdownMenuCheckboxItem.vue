<script setup lang="ts">
import type { DropdownMenuCheckboxItemEmits, DropdownMenuCheckboxItemProps } from "reka-ui"
import type { HTMLAttributes } from "vue"
import { reactiveOmit } from "@vueuse/core"
import { PIcon } from "@/components/PIcon"
import {
  DropdownMenuCheckboxItem,
  DropdownMenuItemIndicator,
  useForwardPropsEmits,
} from "reka-ui"
import { cn } from "@/lib/utils"
import { PTypography } from "@/components/PTypography"

const props = defineProps<DropdownMenuCheckboxItemProps & { class?: HTMLAttributes["class"], description?: string }>()
const emits = defineEmits<DropdownMenuCheckboxItemEmits>()

const delegatedProps = reactiveOmit(props, "class")

const forwarded = useForwardPropsEmits(delegatedProps, emits)
</script>

<template>
  <DropdownMenuCheckboxItem
    v-bind="forwarded"
    :class=" cn(
      'flex gap-2 cursor-default select-none items-center rounded-sm py-1 px-3 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
      'data-[disabled]:text-(--partner-text-disabled)',
      props.class,
    )"
  >
    <div class="flex flex-col gap-0 min-w-0 w-full">
      <div class="flex items-center gap-2">
        <span
          :data-state="modelValue ? 'checked' : 'unchecked'"
          :data-disabled="props.disabled || undefined"
          :class="cn(
            'flex h-3.5 w-3.5 items-center justify-center',
            'rounded-sm border-1 border-(--partner-action-enabled) size-4',
            'data-[state=checked]:bg-(--partner-primary-main) data-[state=checked]:border-(--partner-primary-main)',
            'data-[state=checked]:data-[disabled]:!bg-(--partner-action-disabled) data-[disabled]:!border-(--partner-action-disabled)'
          )"
        >
          <DropdownMenuItemIndicator class="text-(--partner-background-white)">
            <PIcon
              v-if="modelValue === 'indeterminate'"
              name="subtract-custom"
              size="small"
            />
            <PIcon
              v-else
              name="checkmark-custom"
              size="small"
            />
          </DropdownMenuItemIndicator>
        </span>
        <slot />
      </div>
      <PTypography
        v-if="props.description || $slots.description"
        variant="body2"
        truncate
        :class="cn('text-sm text-(--partner-text-secondary) pl-6')"
      >
        <slot name="description">
          {{ description }}
        </slot>
      </PTypography>
    </div>
  </DropdownMenuCheckboxItem>
</template>
