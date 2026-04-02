<script setup lang="ts">
import '@/styles/global.css'
import type { PTypographyProps, PTypographyComponent } from './types'
import { computed, inject, onMounted, ref, type ComputedRef } from 'vue'
import { useTestId } from '@/composables/useTestId'
import { cn } from '@/lib/utils'
import { PTooltip } from '@/components/PTooltip'

// This is a map of typography variants to the corresponding HTML tags, when component is not provided
const VariantMap = {
  h1: 'h1', h2: 'h2', h3: 'h3', h4: 'h4', h5: 'h5', h6: 'h6', 
  headline1: 'p', headline2: 'p', headline3: 'p', body1: 'p', body2: 'p',
  buttonLarge: 'p', buttonMedium: 'p', buttonSmall: 'p',
  inputText: 'p', inputLabel: 'p', helperText: 'p', subhead: 'p', tooltip: 'p'
}
const AlignMap = {inherit: '', center: 'text-center', justify: 'text-justify', left: 'text-left', right: 'text-right'}

const props = withDefaults(defineProps<PTypographyProps>(), {
  variant: 'body1',
  align: 'inherit',
  component: undefined,
  noWrap: false,
  truncate: false,
})

// Inject truncate from parent (e.g., PTableCell)
const parentTruncate = inject<boolean>('truncate', props.truncate)

// Template ref to access the element
const elementRef = ref<HTMLElement>()
const textContent = ref('')

// Truncation observer logic
const isTruncated = ref(false)

function updateTruncation() {
  if (!shouldTruncate.value || !elementRef.value) return
  textContent.value = elementRef.value.textContent || ''
  isTruncated.value = elementRef.value.scrollWidth > elementRef.value.clientWidth
}

onMounted(() => {
  // Read text content after mount
  if (elementRef.value) {
    textContent.value = elementRef.value.textContent || ''
  }
})

const componentTag = computed(() => {
  return props.component ? props.component : VariantMap[props.variant]
}) as ComputedRef<PTypographyComponent>

const variantClass = computed(() => {
  return `partner-${props.variant}`
}) as ComputedRef<string>

const alignClass = computed(() => {
  return AlignMap[props.align]
}) as ComputedRef<string>

const noWrapClass = computed(() => {
  return props.noWrap ? 'text-nowrap' : ''
}) as ComputedRef<string>

const shouldTruncate = computed(() => {
  return props.truncate || parentTruncate
}) as ComputedRef<boolean>

const truncateClass = computed(() => {
  return shouldTruncate.value ? 'truncate' : ''
}) as ComputedRef<string>

// Add aria-label only when truncated
const truncatedText = computed(() => {
  return shouldTruncate.value ? textContent.value : undefined
}) as ComputedRef<string | undefined>

const { testIdAttrs } = useTestId()
</script>

<template>
  <PTooltip :disabled="!isTruncated">
    <template #tooltip-trigger>
      <component
        :is="componentTag"
        ref="elementRef"
        :class="cn('partner-preflight', variantClass, alignClass, noWrapClass, truncateClass, props.class)"
        :aria-label="truncatedText"
        v-bind="testIdAttrs"
        @mouseenter="updateTruncation"
        @focusin="updateTruncation"
      >
        <slot />
      </component>
    </template>
    <template #tooltip-content>
      {{ truncatedText }}
    </template>
  </PTooltip>
</template>