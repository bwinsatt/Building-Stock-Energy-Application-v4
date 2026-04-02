<script setup lang="ts">
import '@/styles/global.css'
import type { PrimitiveProps } from 'reka-ui'
import { computed } from 'vue'
import { Button } from '@/components/shadcn/ui/button'
import { buttonVariants, type ButtonVariants } from './index'
import { cn } from '@/lib/utils'
import type { HTMLAttributes, ComputedRef } from 'vue'
import { PIcon } from '@/components/PIcon'
import { PTypography } from '@/components/PTypography'
import type { PTypographyVariant } from '@/components/PTypography/types'
import type { Size } from '@/types/size'
import { useTestId } from '@/composables/useTestId'

interface Props extends PrimitiveProps {
  variant?: ButtonVariants["variant"]
  appearance?: ButtonVariants['appearance']
  size?: Size
  class?: HTMLAttributes["class"]
  name?: string
  icon?: string
  iconButton?: boolean // Maybe change to "iconOnly"?
  iconPosition?: 'left' | 'right'
  disabled?: boolean
}
export type { Props as PButtonProps }

const props = withDefaults(defineProps<Props>(), {
  variant: 'primary',
  appearance: 'contained',
  size: 'medium',
  icon: undefined,
  iconButton: false,
  iconPosition: 'left',
  disabled: false,
})

const classes = computed(() =>
  cn(
    buttonVariants({
      variant: props.variant,
      appearance: props.appearance,
      size: props.size,
      iconButton: props.iconButton,
    }),
    props.class,
  ),
) as ComputedRef<string>

const sizeMap = {
  small: 'buttonSmall',
  medium: 'buttonMedium',
  large: 'buttonLarge',
} as Record<Size, PTypographyVariant>

const typographyVariant = computed(() => {
  return sizeMap[props.size || 'medium']
})

export interface PButtonEmits {
  (e: 'click', event: MouseEvent): void
}

const emits = defineEmits<PButtonEmits>()

const { testIdAttrs } = useTestId()
</script>
  
<template>
  <Button
    v-bind="testIdAttrs"
    :class="classes"
    :disabled="disabled"
    @click="emits('click', $event)"
  >
    <PIcon
      v-if="icon && iconPosition === 'left'"
      :name="icon"
    />
    <PTypography
      v-if="!iconButton"
      :variant="typographyVariant"
      component="span"
    >
      <slot />
    </PTypography>
    <PIcon
      v-if="icon && iconPosition === 'right'"
      :name="icon"
    />
  </Button>
</template>