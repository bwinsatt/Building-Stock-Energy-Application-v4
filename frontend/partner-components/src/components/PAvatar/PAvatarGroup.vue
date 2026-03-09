<script setup lang="ts">
import '@/styles/global.css'
import { computed, type HTMLAttributes, type ComputedRef } from "vue"
import { cn } from "@/lib/utils"
import { useTestId } from '@/composables/useTestId'
import PAvatar, { type PAvatarProps } from './PAvatar.vue'
import { type TooltipDirections } from '@/components/PTooltip'

export interface PAvatarGroupProps {
  class?: HTMLAttributes["class"],
  avatars: PAvatarProps[],
  size?: PAvatarProps["size"],
  shape?: PAvatarProps["shape"],
  maxVisible?: number,
  spacing?: 'none' | 'default' | 'compact',
  tooltipDirection?: TooltipDirections,
}

const props = withDefaults(defineProps<PAvatarGroupProps>(), {
  maxVisible: 2,
  spacing: 'default',
  tooltipDirection: 'bottom',
})

const maxVisible = computed(() => Math.min(Math.abs(props.maxVisible), 4)) as ComputedRef<number>

const { testIdAttrs } = useTestId()

const zClasses = ['z-50','z-40','z-30','z-20','z-10','z-0'] as const
const stackClass = (index: number) => zClasses.slice(props.avatars.length - maxVisible.value, props.avatars.length)[index] ?? 'z-0'

const titleOverflowText = computed(() => `${props.avatars.slice(maxVisible.value).map(avatar => avatar.name).join('\n')}`) as ComputedRef<string>
const titleOverflowHtml = computed(() => titleOverflowText.value.replace(/\n/g, '<br />')) as ComputedRef<string>

const spacingClasses = {
  none: '',
  default: '-space-x-1',
  compact: '-space-x-2',
} as const
const spacingClass = computed(() => {
  return spacingClasses[props.spacing] ?? ''
}) as ComputedRef<string>
</script>

<template>
  <div
    v-bind="testIdAttrs"
    :class="cn('flex flex-row', spacingClass, props.class)"
  >
    <slot
      v-for="(avatar, index) in props.avatars.slice(0, maxVisible)"
      :key="index"
      name="avatars-visible"
      v-bind="avatar"
    >
      <PAvatar 
        :key="index"
        v-bind="avatar"
        :size="props.size"
        :shape="props.shape"
        :tooltip-direction="props.tooltipDirection"
        :class="stackClass(index)"
      />
    </slot>
    <slot
      v-if="props.avatars.length > maxVisible"
      name="overflow"
    >
      <PAvatar
        :size="props.size"
        :shape="props.shape"
        :initials="`+${props.avatars.length - maxVisible}`"
        :tooltip-direction="props.tooltipDirection"
        :class="stackClass(maxVisible)"
      >
        <template #tooltip-content>
          <p v-html="titleOverflowHtml" />
        </template>
      </PAvatar>
    </slot>
  </div>
</template>