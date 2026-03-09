<script setup lang="ts">
import '@/styles/global.css'
import { computed, ref, watch, type HTMLAttributes, type ComputedRef } from "vue"
import { cn } from "@/lib/utils"
import { PIcon, type PIconProps } from "@/components/PIcon"
import { PTypography, type TypographyVariant } from "@/components/PTypography"
import { useTestId } from '@/composables/useTestId'
import { PTooltip, type TooltipDirections } from '@/components/PTooltip'
import { PBadge, type BadgeVariants } from '@/components/PBadge'
import { getInitials } from '@/utils/strings'

export type PAvatarSize = "small" | "medium" | "large" | "xlarge"
export type PAvatarShape = "square" | "circle"
export type PAvatarBadge = "primary" | "secondary" | "success" | "warning" | "error" | "neutral" 
  | "online" | "green" | "offline" | "gray" | "away" | "yellow" | "busy" | "red" | "blue" | "orange"
export type PAvatarBadgePosition = "top-left" | "top-right" | "bottom-left" | "bottom-right"

export interface PAvatarProps {
  class?: HTMLAttributes["class"],
  size?: PAvatarSize,
  shape?: PAvatarShape,
  badge?: PAvatarBadge,
  badgePosition?: PAvatarBadgePosition,
  image?: string,
  name?: string,
  initials?: string,
  tooltipDirection?: TooltipDirections,
}

const props = withDefaults(defineProps<PAvatarProps>(), {
  tooltipDirection: 'bottom',
})

const { testIdAttrs } = useTestId()

const borderClass = 'border-2 border-(--partner-white)'

const roundedClass = computed(() => {
  return props.shape === 'square' ? 'rounded-sm' : 'rounded-full'
}) as ComputedRef<string>

const sizeClass = computed(() => {
  switch (props.size) {
    case 'small':
      return 'size-6'
    case 'medium':
      return 'size-8'
    case 'large':
      return 'size-10'
    case 'xlarge':
      return 'size-12'
    default:
      return 'size-8'
  }
}) as ComputedRef<string>

const badgeVariantMap = {
  // Semantic
  primary: 'primary',
  secondary: 'secondary',
  success: 'success',
  warning: 'warning',
  error: 'error',
  neutral: 'neutral',

  // Colors
  blue: 'primary',
  orange: 'secondary',
  green: 'success',
  yellow: 'warning',
  red: 'error',
  gray: 'neutral',

  // Activity status
  online: 'success',
  away: 'warning',
  busy: 'error',
  offline: 'neutral',
} as const

const badgeVariant = computed(() => {
  return badgeVariantMap[props.badge as keyof typeof badgeVariantMap] ?? 'primary'
}) as ComputedRef<BadgeVariants['variant']>

const badgePositionClass = computed(() => {
  const badgeOffsets: Record<string, Record<string, string>> = {
    xlarge: {
      'top-left': 'top-0 left-0',
      'top-right': 'top-0 right-0',
      'bottom-left': 'bottom-0 left-0',
      'bottom-right': 'bottom-0 right-0',
    },
    small: {
      'top-left': '-top-1 -left-1',
      'top-right': '-top-1 -right-1',
      'bottom-left': '-bottom-1 -left-1',
      'bottom-right': '-bottom-1 -right-1',
    },
    default: {
      'top-left': '-top-(--partner-spacing-half) -left-(--partner-spacing-half)',
      'top-right': '-top-(--partner-spacing-half) -right-(--partner-spacing-half)',
      'bottom-left': '-bottom-(--partner-spacing-half) -left-(--partner-spacing-half)',
      'bottom-right': '-bottom-(--partner-spacing-half) -right-(--partner-spacing-half)',
    },
  }

  const sizeKey = (props.size === 'xlarge' && props.shape === 'circle') || props.size === 'small' ? props.size : 'default'
  const positionKey = props.badgePosition ?? 'bottom-right'
  return badgeOffsets[sizeKey][positionKey]
}) as ComputedRef<string>

const iconSizeMap = {
  small: 'small',
  medium: 'medium',
  large: 'medium',
  xlarge: 'large',
} as const

const iconSize = computed(() => {
  return iconSizeMap[props.size as keyof typeof iconSizeMap] ?? 'medium'
}) as ComputedRef<PIconProps['size']>

const typographyVariant = computed(() => {
  switch (props.size) {
    case 'small':
      return 'tooltip'
    case 'medium':
      return 'body1'
    case 'large':
      return 'h4'
    case 'xlarge':
      return 'h4'
    default:
      return 'body1'
  }
}) as ComputedRef<TypographyVariant>

const initials = computed(() => {
  if (props.initials) return props.initials.toUpperCase()
  return getInitials(props.name ?? '')
}) as ComputedRef<string>

const imageLoaded = ref(false)

watch(() => props.image, (url) => {
  imageLoaded.value = false
  if (!url) return

  const img = new Image()
  img.onload = () => { imageLoaded.value = true }
  img.onerror = () => { imageLoaded.value = false }
  img.src = url
}, { immediate: true })
</script>

<template>
  <PTooltip
    :direction="props.tooltipDirection"
    :disabled="!props.name && !$slots['tooltip-content']"
  >
    <template #tooltip-trigger>
      <div 
        v-bind="{ ...testIdAttrs, ...$attrs }"
        :style="imageLoaded ? { backgroundImage: `url(${props.image})` } : undefined"
        :class="cn('relative bg-partner-gray-5 select-none text-partner-white flex items-center justify-center bg-cover bg-center', 
                   roundedClass, sizeClass, borderClass, props.class)"
      >
        <slot v-if="!imageLoaded">
          <PTypography
            v-if="initials"
            :variant="typographyVariant"
            component="span"
          >
            <slot name="initials">
              {{ initials }}
            </slot>
          </PTypography>
          <PIcon
            v-else
            name="user-filled"
            :size="iconSize"
          />
        </slot>
        <slot
          v-if="props.badge"
          name="badge"
        >
          <PBadge
            :variant="badgeVariant"
            appearance="dot"
            :class="cn('absolute size-3', badgePositionClass, borderClass)"
          />
        </slot>
      </div>
    </template>
    <template #tooltip-content>
      <slot name="tooltip-content">
        {{ props.name }}
      </slot>
    </template>
  </PTooltip>
</template>