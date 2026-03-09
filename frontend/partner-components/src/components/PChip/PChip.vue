<script setup lang="ts">
import '@/styles/global.css'
import type { HTMLAttributes, ComputedRef } from "vue"
import { computed, useAttrs, ref, watch } from "vue"
import type { ChipVariants } from "."
import { cn } from "@/lib/utils"
import { chipVariants } from "."
import { PIcon } from "@/components/PIcon"
import { PTypography } from "@/components/PTypography"
import { useTestId } from "@/composables/useTestId"

export interface PChipProps {
  variant?: ChipVariants["variant"]
  appearance?: ChipVariants["appearance"]
  size?: ChipVariants["size"]
  class?: HTMLAttributes["class"]
  disabled?: boolean

  removable?: boolean
  removed?: boolean

  selectable?: boolean
  selected?: boolean
}

const props = withDefaults(defineProps<PChipProps>(), {
  variant: 'primary',
  appearance: 'contained',
  size: 'medium',
})

export interface PChipEmits {
  (e: 'remove'): void
  (e: 'select', selected: boolean): void
}

const emits = defineEmits<PChipEmits>()

const attrs = useAttrs()

const { testIdAttrs } = useTestId()

const isDisabled = computed(() => props.disabled || attrs['data-disabled']) as ComputedRef<boolean>

const clickableClass = computed(() => {
  return !isDisabled.value ? 'cursor-pointer select-none pointer-events-auto' : 'pointer-events-none'
}) as ComputedRef<string>

/**
 * Selectable PChip
 */

const selectableClass = computed(() => {
  return props.selectable ? clickableClass.value : 'pointer-events-none'
}) as ComputedRef<string>

const selectedState = ref(props.selected)

watch(() => props.selected, (newVal) => {
  selectedState.value = newVal
})

const handleSelect = () => {
  if (!props.selectable || isDisabled.value) return
  selectedState.value = !selectedState.value
  emits('select', selectedState.value)
}

/**
 * Removable PChip
 */

const removableClass = computed(() => {
  return props.removable ? clickableClass.value : 'pointer-events-none'
}) as ComputedRef<string>

const removedState = ref(props.removed)

watch(() => props.removed, (newVal) => {
  removedState.value = newVal
})

const removedClass = computed(() => {
  return removedState.value ? 'hidden' : ''
}) as ComputedRef<string>

const handleRemove = () => {
  if (!props.removable || isDisabled.value) return
  removedState.value = true
  emits('remove')
}
</script>

<template>
  <div 
    v-bind="testIdAttrs"
    ref="elementRef"
    :class="cn(chipVariants({ variant, appearance, size }), removedClass, selectableClass, props.class)"
    :data-disabled="disabled || undefined"
    :data-selected="selectedState"
    :data-removed="removedState"
    @click.stop="handleSelect"
  >
    <slot name="left" />
    <PTypography
      variant="inputLabel"
      component="span"
    >
      <slot />
    </PTypography>
    <slot name="right" />
    <PIcon
      v-if="props.removable"
      name="close"
      size="small"
      :class="removableClass"
      @click.stop="handleRemove"
    />
  </div>
</template>
