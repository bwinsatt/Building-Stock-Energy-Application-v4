<script setup lang="ts">
import '@/styles/global.css'
import type { CheckboxRootEmits, CheckboxRootProps } from "reka-ui"
import type { HTMLAttributes } from "vue"
import { reactiveOmit } from "@vueuse/core"
import { PIcon } from "@/components/PIcon/"
import { CheckboxIndicator, CheckboxRoot, useForwardPropsEmits } from "reka-ui"
import { cn } from "@/lib/utils"
import { computed, ref, watch, type ComputedRef } from 'vue'
import { PLabel } from '@/components/PLabel'
import { useTestId } from '@/composables/useTestId'
import type { PCheckboxProps, PCheckboxEmits, CheckedState } from '@/components/PCheckbox'

const props = withDefaults(defineProps<PCheckboxProps & CheckboxRootProps & { class?: HTMLAttributes["class"] }>(), {
  checked: false,
  disabled: false,
  indeterminate: false,
  required: false,
  size: 'medium',
})

const emits = defineEmits<PCheckboxEmits & CheckboxRootEmits>()

const delegatedProps = reactiveOmit(props, "class")

const forwarded = useForwardPropsEmits(delegatedProps, emits)

const { testIdAttrs } = useTestId(() => props.id || props.label)

const sizeClass = computed(() => {
  switch (props.size) {
    case 'small':
      return 'py-1'
    case 'medium':
      return 'py-2'
    case 'large':
      return 'py-3'
    default:
      return 'py-2'
  }
}) as ComputedRef<string>

const disabled = computed(() => props.disabled ? true : undefined) as ComputedRef<boolean | undefined>

const hoverClass = computed(() => !props.disabled ? 'hover:ring-3 hover:ring-(--partner-inherit-hovered)' : '') as ComputedRef<string>

const initialChecked = computed(() => props.checked ? true : props.indeterminate ? 'indeterminate' : null) as ComputedRef<CheckedState>

watch(initialChecked, (newVal) => {
  if (checkedState.value != newVal) {
    checkedState.value = newVal
  }
})

const checkedState = ref<CheckedState>(initialChecked.value)

const checkedClass = computed(() => checkedState.value === true || checkedState.value === 'indeterminate' ? 'border-(--partner-primary-main) bg-(--partner-primary-main) disabled:bg-(--partner-text-disabled)' : '') as ComputedRef<string>

const handleChanged = (value: CheckedState) => {
  checkedState.value = value
  if (props.onChange) {
    props.onChange(value)
  }
  emits('changed', value)
}
</script>

<template>
  <div
    :class="cn('partner-preflight flex items-center gap-1', sizeClass, props.class)"
    v-bind="testIdAttrs"
  >
    <div :class="cn('rounded-sm p-1', hoverClass, !props.disabled && 'cursor-pointer')">
      <CheckboxRoot
        v-bind="forwarded"
        :id="id"
        v-model="checkedState"
        :default-value="checkedState || undefined"
        :required="required"
        :disabled="disabled"
        :class="
          cn('grid place-content-center peer h-4 w-4 shrink-0 rounded-(--spacing-half) focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring cursor-pointer disabled:cursor-not-allowed bg-white text-white border border-black disabled:border-(--partner-text-disabled)',
             'bg-(--partner-background-white) border-(--partner-action-enabled)',
             hoverClass,
             checkedClass,
             props.class)"
        @update:model-value="handleChanged"
      >
        <CheckboxIndicator :class="cn('grid place-content-center text-current')">
          <PIcon
            v-if="checkedState === 'indeterminate'"
            name="subtract-custom"
            size="small"
            color="var(--partner-background-white)"
          />
          <PIcon
            v-else-if="checkedState"
            name="checkmark-custom"
            size="small"
            color="var(--partner-background-white)"
          />
        </CheckboxIndicator>
      </CheckboxRoot>
    </div>
    <PLabel
      v-if="label"
      :for="id"
      variant="inputText"
      component="span"
      :class="cn('pt-0.5 text-partner-primary', !props.disabled && 'cursor-pointer')"
      :required="required"
      :disabled="disabled"
    >
      <slot name="label">
        {{ label }}
      </slot>
    </PLabel>
  </div>
</template>
