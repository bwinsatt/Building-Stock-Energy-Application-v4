<script setup lang="ts">
import '@/styles/global.css'
import { type HTMLAttributes, ref, computed } from 'vue'
import { PSelectMenu, type PMenuItemProps } from '@/components/PMenu'
import { cn } from '@/lib/utils'
import type { Size } from '@/types/size'
import { reactiveOmit } from '@vueuse/core'
import { useVModel } from '@vueuse/core'
import { PIcon } from '@/components/PIcon'
import { useInputStyles } from '@/composables/useInputStyles'
import { PInputWrapper } from '@/components/PInputWrapper'
import { useTestId } from '@/composables/useTestId'
import { POverflowGroup } from '@/components/POverflowGroup'
import { PChip, type ChipVariants } from '@/components/PChip'
import { PButton } from '@/components/PButton'

defineOptions({ inheritAttrs: false })

type ModelValue = string | (string)[] | null

export interface PSelectProps {
  class?: HTMLAttributes['class']
  id?: string
  name?: string
  size?: Size
  label?: string
  menuLabel?: string
  helperText?: string
  errorText?: string
  error?: boolean
  searchable?: boolean
  clearable?: boolean
  clearableMenu?: boolean
  required?: boolean
  type?: 'multi' | 'single'
  variant?: 'text' | 'chip'
  chipVariant?: ChipVariants['variant']
  chipAppearance?: ChipVariants['appearance']
  items: PMenuItemProps[]
  hideFooter?: boolean
  defaultValue?: ModelValue
  modelValue?: ModelValue
  placeholder?: string
  disabled?: boolean
}

const props = withDefaults(defineProps<PSelectProps>(), {
  type: 'single',
  variant: 'text',
  chipVariant: 'neutral',
  chipAppearance: 'contained',
  chipSize: 'medium',
  size: 'medium',
  searchable: false,
  hideFooter: true,
  clearable: false,
  clearableMenu: false,
})

const delegatedProps = reactiveOmit(props, "class", "clearable", "clearableMenu")

export interface PSelectEmits {
  (e: 'update:modelValue', value: ModelValue): void
  (e: 'apply', items: PMenuItemProps[]): void
  (e: 'clear'): void
  (e: 'update:open', value: boolean): void
}

const emits = defineEmits<PSelectEmits>()

const modelValue = useVModel(props, 'modelValue', emits, {
  passive: true,
  defaultValue: props.defaultValue ?? props.items.map(item => item.modelValue) as string[],
})

const open = ref(false)

function onApply(items: PMenuItemProps[]) {
  if (props.type === 'single') {
    modelValue.value = items[0]?.label
  } else {
    modelValue.value = items.map(item => item.label) as string[]
  }
  emits('apply', items)
}

function onClear() {
  modelValue.value = props.type === 'single' ? null : []
  emits('clear')
}

function onOpenChange(value: boolean) {
  open.value = value
  emits('update:open', value)
}

function onChipRemove(label: string) {
  if (Array.isArray(modelValue.value)) {
    modelValue.value = modelValue.value.filter(v => v !== label)
  } else {
    modelValue.value = null
  }
}

const { inputClass } = useInputStyles(props)

const { testIdAttrs } = useTestId()

const selectedLabels = computed(() => {
  if (!modelValue.value) return []
  if (Array.isArray(modelValue.value)) return modelValue.value.filter(Boolean).map(item => item as string)
  return [modelValue.value as string]
})
</script>

<template>
  <PInputWrapper v-bind="props">
    <div class="relative flex items-center">
      <PSelectMenu
        v-bind="delegatedProps"
        :model-value="modelValue"
        :label="menuLabel"
        :open="open"
        :clearable="clearableMenu"
        @apply="onApply"
        @clear="onClear"
        @update:open="onOpenChange"
      >
        <template #trigger>
          <button
            v-bind="{...testIdAttrs, ...$attrs}"
            :id="id"
            :class="cn(inputClass, 'flex items-center gap-1 min-w-11.5 text-left',
                       open && 'border-(--partner-border-active) ring-1 ring-(--partner-border-active)',
                       open && error && 'border-(--partner-error-main) ring-(--partner-error-main)',
                       props.class)"
            :disabled="disabled"
          >
            <POverflowGroup
              v-if="selectedLabels.length > 0"
              truncate
              class="flex-1 min-w-0 gap-1"
            >
              <template v-if="variant === 'chip'">
                <PChip
                  v-for="(item) in selectedLabels"
                  :key="item"
                  :variant="chipVariant"
                  :appearance="chipAppearance"
                  :size="size"
                  removable
                  :label="item"
                  class="shrink-0 whitespace-nowrap"
                  @remove="onChipRemove(item)"
                >
                  {{ item }}
                </PChip>
              </template>
              <template v-else>
                <span
                  v-for="(item, index) in selectedLabels"
                  :key="item"
                  class="shrink-0 whitespace-nowrap"
                >
                  {{ item }}{{ index < selectedLabels.length - 1 ? ',' : '' }}
                </span>
              </template>
            </POverflowGroup>
            <span
              v-else
              class="flex-1 min-w-0 text-(--partner-text-placeholder) truncate"
            >
              {{ placeholder }}
            </span>
            <PIcon
              name="chevron-down"
              size="small"
              :class="cn('shrink-0 text-(--partner-action-enabled)', clearable && 'pl-8', open && '[&>svg]:rotate-180')"
            />
          </button>
        </template>
      </PSelectMenu>
      <PButton
        v-if="clearable"
        :disabled="disabled"
        type="button"
        aria-label="Clear"
        variant="neutral"
        appearance="text"
        size="small"
        icon="close-large"
        icon-button
        class="absolute right-8"
        @click.stop="onClear"
      />
    </div>
  </PInputWrapper>
</template>