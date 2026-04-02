<script setup lang="ts">
import '@/styles/global.css'
import { ref, onMounted, onUnmounted, nextTick, watch, type HTMLAttributes } from 'vue'
import { cn } from '@/lib/utils'
import { useTestId } from '@/composables/useTestId'

export interface POverflowGroupProps {
  class?: HTMLAttributes['class']
  truncate?: boolean
}

const props = withDefaults(defineProps<POverflowGroupProps>(), {
  truncate: true,
})

const containerRef = ref<HTMLElement | null>(null)
const countRef = ref<HTMLElement | null>(null)
const overflowCount = ref(0)

function update() {
  const container = containerRef.value
  if (!container) return

  const countEl = countRef.value
  const children = Array.from(container.children).filter(
    el => el !== countEl,
  ) as HTMLElement[]

  for (const child of children) {
    child.style.removeProperty('display')
    child.style.removeProperty('max-width')
    child.style.removeProperty('overflow')
    child.style.removeProperty('text-overflow')
  }

  if (children.length === 0) {
    overflowCount.value = 0
    return
  }

  const containerRight = container.getBoundingClientRect().right

  let anyOverflow = false
  for (const child of children) {
    if (child.getBoundingClientRect().right > containerRight) {
      anyOverflow = true
      break
    }
  }

  if (!anyOverflow) {
    overflowCount.value = 0
    return
  }

  const reservedWidth = countEl?.offsetWidth ?? 0
  const effectiveRight = containerRight - reservedWidth

  let visibleCount = 0
  for (const child of children) {
    if (child.getBoundingClientRect().right > effectiveRight) break
    visibleCount++
  }

  const firstOverflow = children[visibleCount]
  const canTruncate = props.truncate && firstOverflow &&
    firstOverflow.getBoundingClientRect().left < effectiveRight

  overflowCount.value = children.length - visibleCount - (canTruncate ? 1 : 0)

  for (let i = 0; i < children.length; i++) {
    if (i < visibleCount) continue

    if (i === visibleCount && canTruncate) {
      const left = children[i].getBoundingClientRect().left
      children[i].style.maxWidth = `${effectiveRight - left}px`
      children[i].style.overflow = 'hidden'
      children[i].style.textOverflow = 'ellipsis'
      continue
    }

    children[i].style.display = 'none'
  }
}

watch(() => props.truncate, () => nextTick(update))

let resizeObserver: ResizeObserver | null = null
let mutationObserver: MutationObserver | null = null

onMounted(() => {
  const el = containerRef.value
  if (!el) return

  resizeObserver = new ResizeObserver(() => update())
  resizeObserver.observe(el)

  mutationObserver = new MutationObserver(() => nextTick(update))
  mutationObserver.observe(el, { childList: true })

  nextTick(update)
})

onUnmounted(() => {
  resizeObserver?.disconnect()
  mutationObserver?.disconnect()
})

const { testIdAttrs } = useTestId()
</script>

<template>
  <div
    v-bind="testIdAttrs"
    :class="cn('partner-preflight relative overflow-hidden flex items-center', props.class)"
  >
    <div
      ref="containerRef"
      class="flex-1 overflow-hidden flex items-center min-w-0 gap-1"
    >
      <slot />
    </div>
    <span
      v-if="overflowCount > 0"
      ref="countRef"
      class="absolute right-0 top-0 bottom-0 flex items-center pl-1 bg-background"
    >
      +{{ overflowCount }}
    </span>
  </div>
</template>
