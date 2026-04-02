<script setup lang="ts">
import '@/styles/global.css'
import type { CheckboxGroupRootEmits, CheckboxGroupRootProps, AcceptableValue } from "reka-ui"
import type { HTMLAttributes } from "vue"
import { reactiveOmit } from "@vueuse/core"
import { CheckboxGroupRoot, useForwardPropsEmits } from "reka-ui"
import { cn } from "@/lib/utils"
import { computed, watch, type ComputedRef } from 'vue'
import { useVModel } from '@vueuse/core'
import { useTestId } from '@/composables/useTestId'
import { 
  PCheckbox, 
  type PCheckboxGroupItemProps, 
  type PCheckboxGroupProps, 
  type PCheckboxGroupEmits 
} from '@/components/PCheckbox'
import { PInputWrapper } from '@/components/PInputWrapper'

const props = withDefaults(defineProps<PCheckboxGroupProps & CheckboxGroupRootProps & { class?: HTMLAttributes["class"] }>(), {
  label: '',
  orientation: 'vertical',
  class: '',
  checkboxes: () => [] as PCheckboxGroupItemProps[],
  disabled: false,
  required: false,
  size: 'medium',
  error: false,
})

const emits = defineEmits<CheckboxGroupRootEmits & PCheckboxGroupEmits>()

const delegatedProps = reactiveOmit(props, "class", "checkboxes", "label", "modelValue")

const forwarded = useForwardPropsEmits(delegatedProps, emits)

const { testIdAttrs } = useTestId(() => props.label)

const orientationClass = computed(() => 
  props.orientation === 'horizontal' ? 'flex flex-row gap-4' : 'flex flex-col gap-0'
) as ComputedRef<string>

const getCheckboxIdentifier = (checkbox: PCheckboxGroupItemProps, index: number): AcceptableValue => 
  checkbox.label || `checkbox-${index}`

// Track which checkboxes are checked in the group
const checkedValues = useVModel(props, 'modelValue', emits, {
  passive: true,
  defaultValue: props.checkboxes
    .filter(cb => cb.checked || cb.indeterminate)
    .map((cb, idx) => getCheckboxIdentifier(cb, idx)),
})

// Emit changed event when checkedValues changes
watch(checkedValues, (newValues) => {
  const changedCheckboxes = props.checkboxes.map((checkbox, index) => ({
    ...checkbox,
    checked: newValues?.includes(getCheckboxIdentifier(checkbox, index)) ?? false
  }))
  if (props.onChange) {
    props.onChange(changedCheckboxes)
  }
  emits('changed', changedCheckboxes)
})
</script>
  
<template>
  <PInputWrapper v-bind="props">
    <CheckboxGroupRoot 
      v-bind="{...testIdAttrs, ...forwarded}" 
      v-model="checkedValues"
      :class="cn(orientationClass, props.class)"
      data-testid="checkbox-group"
    >
      <PCheckbox 
        v-for="(checkbox, index) in checkboxes" 
        :id="checkbox.id || checkbox.label"
        :key="index"
        :value="getCheckboxIdentifier(checkbox, index)"
        :checked="checkedValues?.includes(getCheckboxIdentifier(checkbox, index)) ?? false" 
        :disabled="checkbox.disabled || props.disabled" 
        :size="size" 
        :label="checkbox.label" 
      />
    </CheckboxGroupRoot>
  </PInputWrapper>
</template>