<script setup lang="ts">
import '@/styles/global.css'
import type { HTMLAttributes } from 'vue'
import { useTestId } from '@/composables/useTestId'
import { badgeVariants, type BadgeVariants } from './index'
import { cn } from '@/lib/utils'
import { PTypography } from '@/components/PTypography'

export interface PBadgeProps {
  class?: HTMLAttributes["class"]
  variant?: BadgeVariants["variant"],
  appearance?: BadgeVariants["appearance"]
}

const props = defineProps<PBadgeProps>()

const { testIdAttrs } = useTestId()
</script>

<template>
  <div
    v-bind="testIdAttrs"
    :class="cn(badgeVariants({ variant: props.variant, appearance: props.appearance }), props.class)"
  >
    <PTypography
      v-if="props.appearance !== 'dot'"
      variant="headline3"
      component="span"
    >
      <slot />
    </PTypography>
  </div>
</template>