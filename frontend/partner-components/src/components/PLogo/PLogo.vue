<script setup lang="ts">
import '@/styles/global.css'
import { computed } from 'vue'
import { nameToFile, type LogoName } from './logoConstants'
import { useTestId } from '@/composables/useTestId'

interface Props {
  logoName: LogoName,
  name?: string,
  width?: string,
  height?: string,
  alt?: string
}

const props = defineProps<Props>()

// Preload all logo assets and create filename-to-URL map
const logoUrlMap = Object.fromEntries(
  Object.entries(
    import.meta.glob('@/assets/logos/*.svg', {
      query: '?url',
      import: 'default',
      eager: true,
    }) as Record<string, string>
  ).map(([path, url]) => {
    const fileName = path.split('/').pop()?.replace('.svg', '') || ''
    return [fileName, url]
  })
) as Record<string, string>

const fileName = computed(() => {
  const normalized = props.logoName.trim()
  return nameToFile[normalized] || nameToFile[normalized.toLowerCase()] || normalized.toLowerCase().replace(/\s+/g, '-')
})

const src = computed<string>(() => {
  return logoUrlMap[fileName.value] || ''
})

// Every component will have a data-testid attribute for testing purposes
const { testIdAttrs } = useTestId(() => fileName.value)
</script>
  
<template>
  <img
    :src="src"
    :width="props.width"
    :height="props.height"
    :alt="props.alt"
    v-bind="testIdAttrs"
  >
</template>