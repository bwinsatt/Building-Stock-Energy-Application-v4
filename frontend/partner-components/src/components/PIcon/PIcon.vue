<script setup lang="ts">
import '@/styles/global.css'
import { computed, h } from 'vue'
import { sizeMap, type PIconProps } from './types'
import { findIcon } from './icons'
import { Icon } from '@iconify/vue'
import { useTestId } from '@/composables/useTestId'
import { cn } from '@/lib/utils'

const props = withDefaults(defineProps<PIconProps>(), {
  size: 'medium',
  color: 'currentColor',
})

const { testIdAttrs } = useTestId()

const iconAttrs = computed(() => {
  // if no size is provided, default to medium (24px) - the default icon size per design system
  const sizeValue = sizeMap[props.size as keyof typeof sizeMap] || props.size || sizeMap.medium
  return {
    width: props.width || sizeValue,
    height: props.height || sizeValue,
    color: props.color || 'currentColor'
  }
})

const CustomIcon = computed(() => {
  const svg = findIcon(props.name)
  if (!svg) return null
  
  // Extract viewBox and other attributes from SVG string
  const viewBoxMatch = svg.match(/viewBox="([^"]+)"/)
  const viewBox = viewBoxMatch ? viewBoxMatch[1] : '0 0 24 24'
  
  // Extract inner content (everything between <svg> tags)
  const contentMatch = svg.match(/<svg[^>]*>(.*?)<\/svg>/s)
  const content = contentMatch ? contentMatch[1] : ''
  
  return () => {
    const { width, height, color } = iconAttrs.value
    return h('svg', {
      viewBox,
      width,
      height,
      xmlns: 'http://www.w3.org/2000/svg',
      fill: 'none',
      style: { color },
      innerHTML: content
    })
  }
})

const carbonIcon = computed(() => `carbon:${props.name}`)
</script>

<template>
  <div
    v-bind="testIdAttrs"
    :data-customiconfound="CustomIcon ? 'true' : 'false'"
    :class="cn('partner-preflight inline-block align-middle', props.class)"
  >
    <component
      :is="CustomIcon"
      v-if="CustomIcon"
    />
    <Icon
      v-else
      :icon="carbonIcon"
      v-bind="iconAttrs"
    />
  </div>
</template>