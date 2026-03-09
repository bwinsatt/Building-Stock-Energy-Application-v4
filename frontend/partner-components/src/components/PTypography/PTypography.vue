<script setup lang="ts">
import '@/styles/global.css'
import type { TypographyProps, TypographyComponent } from './types'
import { computed, inject, onMounted, ref, type ComputedRef } from 'vue'
import { useTestId } from '@/composables/useTestId'
import { cn } from '@/lib/utils'

// This is a map of typography variants to the corresponding HTML tags, when component is not provided
const VariantMap = {
  h1: 'h1', h2: 'h2', h3: 'h3', h4: 'h4', h5: 'h5', h6: 'h6', 
  headline1: 'p', headline2: 'p', headline3: 'p', body1: 'p', body2: 'p',
  buttonLarge: 'p', buttonMedium: 'p', buttonSmall: 'p',
  inputText: 'p', inputLabel: 'p', helperText: 'p', subhead: 'p', tooltip: 'p'
}
const AlignMap = {inherit: '', center: 'text-center', justify: 'text-justify', left: 'text-left', right: 'text-right'}

const props = withDefaults(defineProps<TypographyProps>(), {
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

// Read text content after mount
onMounted(() => {
  if (elementRef.value) {
    textContent.value = elementRef.value.textContent || ''
  }
})

const componentTag = computed(() => {
  return props.component ? props.component : VariantMap[props.variant]
}) as ComputedRef<TypographyComponent>

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
  <component
    :is="componentTag"
    ref="elementRef"
    :class="cn(variantClass, alignClass, noWrapClass, truncateClass, props.class)"
    :aria-label="truncatedText"
    :title="truncatedText"
    v-bind="testIdAttrs"
  >
    <slot />
  </component>
</template>