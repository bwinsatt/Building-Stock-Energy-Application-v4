<script setup lang="ts">
import { computed, useSlots, type HTMLAttributes, type ComputedRef } from "vue"
import type { PAlertVariants } from "."
import { cn } from "@/lib/utils"
import { alertVariants } from "."
import { PIcon } from "@/components/PIcon"
import type { Size } from "@/types/size"
import { PTypography, type PTypographyVariant } from "@/components/PTypography"
import { PButton, type ButtonVariants, type PButtonProps } from "@/components/PButton"
import { useTestId } from "@/composables/useTestId"

export interface PAlertProps {
  class?: HTMLAttributes["class"]
  variant?: PAlertVariants["variant"]
  appearance?: PAlertVariants["appearance"]
  size?: PAlertVariants["size"]
  icon?: string
  hideIcon?: boolean
  title?: string
  description?: string
  align?: 'start' | 'center' | 'end'
  hideCloseButton?: boolean
  actionButtonProps?: PButtonProps
  actionButtonText?: string
  closeButtonProps?: PButtonProps
}

const props = withDefaults(defineProps<PAlertProps>(), {
  variant: 'default',
  appearance: 'contained',
  size: 'medium',
})

export interface PAlertEmits {
  (e: 'close', event: MouseEvent): void
  (e: 'action', event: MouseEvent): void
}

const emits = defineEmits<PAlertEmits>()

const slots = useSlots() 

const hasTitle = computed(() => props.title || slots.title ? true : false) as ComputedRef<boolean>

const alignClass = computed(() => {
  switch (props.align) {
    case 'center':
      return 'justify-center text-center'
    case 'end':
      return 'justify-end text-end'
    case 'start':
    default:
      return 'justify-start'
  }
}) as ComputedRef<string>

const iconName = computed(() => {
  switch (props.variant) {
    case 'error':
      return 'warning-filled'
    case 'warning':
      return 'warning-alt-filled'
    case 'success':
      return 'checkmark-filled'
    case 'default':
    case 'info':
    case 'primary':
    case 'secondary':
    case 'neutral':
    default:
      return 'information-filled'
  }
}) as ComputedRef<string>

const iconSize = computed(() => {
  switch (props.size) {
    case 'large':
      return 'medium'
    default:
      return 'small'
  }
}) as ComputedRef<Size>

const titleVariantMap = {
  small: 'headline1',
  medium: 'h5',
  large: 'h4',
} as Record<Size, PTypographyVariant>

const descriptionVariantMap = {
  small: 'body2',
  medium: 'body1',
  large: 'body1',
} as Record<Size, PTypographyVariant>

const descriptionPaddingClass = computed(() => {
  if (props.hideIcon || !hasTitle.value) return ''
  let paddingClass = ''
  switch (props.size) {
    case 'large':
      paddingClass = 'pl-8'
      break
    case 'medium':
    default:
      paddingClass = 'pl-6'
  }
  return !props.align || props.align === 'start' ? paddingClass : ''
}) as ComputedRef<string>

const contentPaddingClass = computed(() => {
  switch (props.size) {
    case 'large':
      return 'py-2'
    case 'medium':
      return 'py-1'
    default:
      return 'py-0.5'
  }
}) as ComputedRef<string>

const buttonPaddingClass = computed(() => {
  switch (props.size) {
    case 'large':
      return 'py-1.5'
    case 'medium':
      return 'py-0.5'
    default:
      return 'py-0'
  }
}) as ComputedRef<string>

const buttonAppearance = computed(() => {
  return props.appearance === 'outlined' || props.appearance === 'underline' ? 'text' : 'contained'
}) as ComputedRef<ButtonVariants["appearance"]>

const buttonVariant = computed(() => {
  switch (props.variant) {
    case 'default':
    case 'info':
    case 'primary':
      return 'primary'
    default:
      return props.variant
  }
}) as ComputedRef<ButtonVariants["variant"]>

const buttonProps = computed(() => {
  return {
    size: 'small',
    variant: buttonVariant.value,
    appearance: buttonAppearance.value,
  }
}) as ComputedRef<PButtonProps>

const closeButtonProps = computed(() => {
  return {
    ...buttonProps.value,
    icon: 'close-large',
    iconButton: true,
    ...props.closeButtonProps,
  }
}) as ComputedRef<PButtonProps>

const computedActionButtonProps = computed(() => {
  return {
    ...buttonProps.value,
    ...props.actionButtonProps,
  }
}) as ComputedRef<PButtonProps>

const onClose = (event: MouseEvent) => {
  emits('close', event)
}

const { testIdAttrs } = useTestId()
</script>

<template>
  <div
    :class="cn(alertVariants({ variant, appearance, size }), props.class)"
    role="alert"
    v-bind="testIdAttrs"
  >
    <div class="flex flex-row gap-2">
      <div :class="cn('flex flex-wrap gap-x-2 items-center w-full', contentPaddingClass, alignClass)">
        <slot name="icon">
          <PIcon
            v-if="!hideIcon"
            :name="icon ?? iconName"
            :size="iconSize"
          />
        </slot>
        <div
          v-if="hasTitle"
          :class="props.align === 'center' || props.align === 'end' ? '' : 'flex-1'"
        >
          <slot name="title">
            <PTypography
              v-if="title"
              :variant="titleVariantMap[props.size || 'medium']"
            >
              {{ title }}
            </PTypography>
          </slot>
        </div>
        <div
          :class="cn(descriptionPaddingClass,
                     hasTitle ? 'basis-full' : '',
                     props.align === 'center' ? 'text-center' : '',
          )"
        >
          <slot name="description">
            <PTypography
              v-if="description"
              :variant="descriptionVariantMap[props.size || 'medium']"
              component="p"
            >
              {{ description }}
            </PTypography>
          </slot>
        </div>
      </div>
      <div :class="cn('flex flex-row gap-2', buttonPaddingClass)">
        <slot
          name="action"
          v-bind="computedActionButtonProps"
        >
          <PButton
            v-if="actionButtonProps || actionButtonText"
            ref="actionButton"
            v-bind="computedActionButtonProps"
            @click="emits('action', $event)"
          >
            <slot name="action-text">
              {{ actionButtonText }}
            </slot>
          </PButton>
        </slot>
        <slot
          name="close"
          v-bind="closeButtonProps"
        >
          <PButton
            v-if="!hideCloseButton"
            ref="closeButton"
            aria-label="Close"
            v-bind="closeButtonProps"
            @click="onClose"
          />
        </slot>
      </div>
    </div>
  </div>
</template>
