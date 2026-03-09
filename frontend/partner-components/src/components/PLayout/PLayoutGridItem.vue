<script setup lang="ts">
import '@/styles/global.css'
import { useTestId } from '@/composables/useTestId'

interface Props {
  name?: string,
}

defineProps<Props>()

const { testIdAttrs } = useTestId()
</script>

<template>
  <div 
    class="col-span-full min-w-0 overflow-hidden break-words"
    v-bind="testIdAttrs"
  >
    <slot />
  </div>
</template>