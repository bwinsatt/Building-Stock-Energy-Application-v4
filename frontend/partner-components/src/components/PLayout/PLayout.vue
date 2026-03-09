<script setup lang="ts">
import '@/styles/global.css'
import { ref, onMounted, onUnmounted } from 'vue'
import PLayoutGrid from './PLayoutGrid.vue'
import { useTestId } from '@/composables/useTestId'
import PIcon from '@/components/PIcon/PIcon.vue'

interface Props { 
  header: boolean,
  leftPanel: boolean,
  rightPanel: boolean,
  footer: boolean,
  name?: string,
  // Custom gutter values per breakpoint (overrides design system defaults)
  // Examples: "24px", "1.5rem", "var(--custom-gutter)"
  gutterSm?: string,
  gutterMd?: string,
  gutterLg?: string,
  gutterXl?: string,
}

const props = withDefaults(defineProps<Props>(), {
  header: true,
  leftPanel: true,
  rightPanel: false,
  footer: false, // Not defined in Design System
  gutterSm: undefined,
  gutterMd: undefined,
  gutterLg: undefined,
  gutterXl: undefined,
})

const leftPanelVisible = ref(false)
const rightPanelVisible = ref(false)
const leftPanelRef = ref<HTMLElement | null>(null)
const rightPanelRef = ref<HTMLElement | null>(null)

const emit = defineEmits<{
  (e: 'left-panel-hidden'): void;
  (e: 'left-panel-shown'): void;
  (e: 'right-panel-hidden'): void;
  (e: 'right-panel-shown'): void;
}>();

const panelStates = { left: false, right: false }
const observer = ref<ResizeObserver | null>(null)

const checkPanelVisibility = () => {
 // Check left panel
 if (leftPanelRef.value && props.leftPanel) {
    const isVisible = leftPanelRef.value.offsetWidth > 0
    if (isVisible !== panelStates.left) {
      if (isVisible) {
        emit('left-panel-shown')
      } else {
        emit('left-panel-hidden')
      }
      panelStates.left = isVisible
    }
  }
  
  // Check right panel
  if (rightPanelRef.value && props.rightPanel) {
    const isVisible = rightPanelRef.value.offsetWidth > 0
    if (isVisible !== panelStates.right) {
      if (isVisible) {
        emit('right-panel-shown')
      } else {
        emit('right-panel-hidden')
      }
      panelStates.right = isVisible
    }
  }
}

onMounted(() => {
  observer.value = new ResizeObserver(() => checkPanelVisibility())
  if (leftPanelRef.value) observer.value.observe(leftPanelRef.value)
  if (rightPanelRef.value) observer.value.observe(rightPanelRef.value)
  checkPanelVisibility()
})

onUnmounted(() => {
  observer.value?.disconnect()
})

// Every component will have a data-testid attribute for testing purposes
const { testIdAttrs } = useTestId()
</script>

<template>
  <div
    class="border border-charcoal-5 flex flex-col h-full w-full"
    v-bind="testIdAttrs"
  >
    <!-- Header -->
    <div 
      v-if="header"
      class="border-b border-charcoal-5 h-[53px] shrink-0 w-full grid grid-cols-[1fr_auto_1fr] items-center overflow-x-hidden"
    >
      <div class="flex items-center justify-start px-4">
        <slot
          v-if="leftPanel"
          name="left-panel-toggle"
        >
          <!-- Left Panel toggle placeholder -->
          <PIcon
            :name="leftPanelVisible ? 'side-panel-close' : 'side-panel-open'"
            class="md:hidden"
            @click="leftPanelVisible = !leftPanelVisible"
          />
        </slot>
      </div>
      <div class="flex items-center justify-center">
        <slot name="header">
          <!-- Header placeholder -->
        </slot>
      </div>
      <div class="flex items-center justify-end px-4">
        <slot
          v-if="rightPanel"
          name="right-panel-toggle"
        >
          <!-- Right Panel toggle placeholder -->
          <PIcon
            :name="rightPanelVisible ? 'right-panel-close' : 'right-panel-open'"
            class="md:hidden"
            @click="rightPanelVisible = !rightPanelVisible"
          />
        </slot>
      </div>
    </div>

    <!-- Container: Left Panel + Body + Right Panel -->
    <div class="flex flex-1 min-h-0 min-w-0 w-full relative">
      <!-- Left Panel (Mobile: Absolute Overlay, Desktop: Normal Flex) -->
      <div 
        v-if="leftPanel && (leftPanelVisible || 'md')"
        ref="leftPanelRef"
        :class="[
          'border-r border-charcoal-5 h-full w-[250px] shrink-0 flex items-center justify-center',
          leftPanelVisible ? 'absolute md:relative left-0 top-0 z-10 bg-background' : 'hidden md:flex'
        ]"
      >
        <slot name="left-panel">
          <!-- Left Panel placeholder -->
        </slot>
      </div>

      <!-- Body / Main Content -->
      <div 
        class="flex flex-1 flex-col min-h-0 min-w-0 overflow-y-auto"
      >
        <div class="py-[var(--breakpoint-sm-padding-tb)] md:py-[var(--breakpoint-md-padding-tb)] lg:py-[var(--breakpoint-lg-padding-tb)] xl:py-[var(--breakpoint-xl-padding-tb)]">
          <PLayoutGrid 
            :gutter-sm="gutterSm"
            :gutter-md="gutterMd"
            :gutter-lg="gutterLg"
            :gutter-xl="gutterXl"
          >
            <slot name="body">
              <!-- Grid items go here -->
            </slot>
          </PLayoutGrid>
        </div>
      </div>

      <!-- Right Panel (Mobile: Absolute Overlay, Desktop: Normal Flex) -->
      <div 
        v-if="rightPanel && (rightPanelVisible || 'md')"
        ref="rightPanelRef"
        :class="[
          'border-l border-charcoal-5 h-full w-[250px] shrink-0 flex items-center justify-center',
          rightPanelVisible ? 'absolute md:relative right-0 top-0 z-10 bg-background' : 'hidden md:flex'
        ]"
      >
        <slot name="right-panel">
          <!-- Right Panel placeholder -->
        </slot>
      </div>
    </div>

    <!-- Footer -->
    <div 
      v-if="footer"
      class="shrink-0 w-full"
    >
      <slot name="footer">
        <!-- Footer placeholder -->
      </slot>
    </div>
  </div>
</template>