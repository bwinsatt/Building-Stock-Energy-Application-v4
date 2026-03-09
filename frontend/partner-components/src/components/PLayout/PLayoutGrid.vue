<script setup lang="ts">
import '@/styles/global.css'
import { computed } from 'vue'
import { useTestId } from '@/composables/useTestId'

interface Props {
  name?: string,
  // Custom gutter values per breakpoint (overrides design system defaults)
  // Examples: "24px", "1.5rem", "var(--custom-gutter)"
  gutterSm?: string,
  gutterMd?: string,
  gutterLg?: string,
  gutterXl?: string,
}

const props = withDefaults(defineProps<Props>(), {
  gutterSm: undefined,
  gutterMd: undefined,
  gutterLg: undefined,
  gutterXl: undefined,
})

// Compute gutter values - use custom if provided, otherwise use design system defaults
const gutterSmValue = computed(() => props.gutterSm || 'var(--breakpoint-sm-gutters)')
const gutterMdValue = computed(() => props.gutterMd || 'var(--breakpoint-md-gutters)')
const gutterLgValue = computed(() => props.gutterLg || 'var(--breakpoint-lg-gutters)')
const gutterXlValue = computed(() => props.gutterXl || 'var(--breakpoint-xl-gutters)')

// Every component will have a data-testid attribute for testing purposes
const { testIdAttrs } = useTestId()
</script>

<template>
  <!-- Grid Container with breakpoint-aware margins -->
  <div 
    class="flex-1 min-h-0 min-w-0 overflow-x-hidden
           mx-[var(--breakpoint-sm-margin-lr)] md:mx-[var(--breakpoint-md-margin-lr)] lg:mx-[var(--breakpoint-lg-margin-lr)] xl:mx-[var(--breakpoint-xl-margin-lr)]"
    v-bind="testIdAttrs"
  >
    <!-- Grid that uses breakpoint-defined columns and gutters -->
    <div 
      class="grid min-h-0 min-w-0 w-full auto-rows-auto
             [grid-template-columns:var(--grid-cols-sm)] md:[grid-template-columns:var(--grid-cols-md)] lg:[grid-template-columns:var(--grid-cols-lg)] xl:[grid-template-columns:var(--grid-cols-xl)]
             gap-[var(--gutter-sm)] md:gap-[var(--gutter-md)] lg:gap-[var(--gutter-lg)] xl:gap-[var(--gutter-xl)]"
      :style="{
        '--gutter-sm': gutterSmValue,
        '--gutter-md': gutterMdValue,
        '--gutter-lg': gutterLgValue,
        '--gutter-xl': gutterXlValue,
      }"
    >
      <slot>
        <!-- Grid items go here -->
      </slot>
    </div>
  </div>
</template>

