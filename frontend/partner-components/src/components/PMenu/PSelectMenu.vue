<script setup lang="ts">
import { PMenu, PMenuItem, type PMenuItemProps, type PMenuProps } from '.'
import { PButton } from '@/components/PButton'
import { computed, reactive, ref, watch, nextTick, type HTMLAttributes } from 'vue'
import { cn } from '@/lib/utils'
import type { Size } from '@/types/size'
import { reactiveOmit } from '@vueuse/core'
import { useTestId } from '@/composables/useTestId'

export interface PSelectMenuProps {
  class?: HTMLAttributes['class']
  size?: Size
  searchable?: boolean
  disableSearchFilter?: boolean
  clearable?: boolean
  required?: boolean
  type: 'multi' | 'single'
  items: PMenuItemProps[]
  hideFooter?: boolean
  hideSelectAll?: boolean
  modelValue?: string | (string)[] | null
  closeOnApply?: boolean
  searchDebounce?: number
  selectedCountOverride?: number
  scrollIntoView?: boolean
  scrollIntoViewOptions?: {
    block?: 'start' | 'end' | 'center' | 'nearest'
    inline?: 'start' | 'end' | 'center' | 'nearest'
    behavior?: 'auto' | 'smooth'
  }
}

const props = withDefaults(defineProps<PSelectMenuProps & PMenuProps>(), {
  size: 'medium',
  searchable: true,
  clearable: true,
  closeOnApply: true,
  scrollIntoView: true,
  scrollIntoViewOptions: () => ({
    block: 'center',
    inline: 'center',
    behavior: 'auto',
  }),
})

const delegatedProps = reactiveOmit(props, "class", "open")

export interface PSelectMenuEmits {
  (e: 'clear'): void
  (e: 'apply', selectedItems: PMenuItemProps[]): void
  (e: 'select', selectedItem: PMenuItemProps): void
  (e: 'update:open', value: boolean): void
  (e: 'update:debouncedSearch', value: string): void
  (e: 'search', value: string): void
}

const emits = defineEmits<PSelectMenuEmits>()

const selectedItems = reactive(new Set<PMenuItemProps>())

watch(
  [() => props.items, () => props.modelValue],
  ([items, value]) => {
    selectedItems.clear()
    if (value === undefined) {
      items.filter(i => i.modelValue).forEach(i => selectedItems.add(i))
      return
    }
    if (!value) return
    const labels = Array.isArray(value) ? value : [value]
    for (const item of items) {
      if (labels.includes(item.label as string)) selectedItems.add(item)
    }
  },
  { immediate: true },
)

const selectedCount = computed(() => selectedItems.size)

function onUpdateModelValue(value: string | boolean, item: PMenuItemProps) {
  selectedItems[value === true ? 'add' : 'delete'](item)
}

const allSelected = computed(() => props.items.filter(item => !item.disabled).every(item => selectedItems.has(item)))

const selectAllState = computed<boolean | 'indeterminate'>(() => {
  if (selectedItems.size === 0) return false
  if (selectedItems.size === props.items.length) return true
  return 'indeterminate'
})

let hasScrolled = false

const vScrollIntoView = {
  mounted(el: HTMLElement, binding: { value: boolean }) {
    if (binding.value && !hasScrolled) {
      hasScrolled = true
      nextTick(() => el.scrollIntoView(props.scrollIntoViewOptions))
    }
  },
}

const open = ref(props.defaultOpen ?? false)

watch(() => props.open, (value) => {
  if (value !== undefined) open.value = value
})

function updateOpen(value: boolean) {
  open.value = value
  emits('update:open', value)
  hasScrolled = false
}

function onOpenChange(value: boolean) {
  updateOpen(value)

  if (props.hideFooter && !value && props.type === 'multi') {
    // If the footer is hidden (Apply button unavailable), we should automatically apply when items are selected
    onApply()
  }
}

function onToggleAll() {
  if (allSelected.value) {
    selectedItems.clear()
  } else {
    props.items.filter(item => !item.disabled).forEach(item => selectedItems.add(item))
  }
}

function onClear() {
  selectedItems.clear()
  emits('clear')
}

const applyButton = ref<HTMLElement | null>(null)

function onApply() {
  emits('apply', [...selectedItems])
  if (props.closeOnApply && applyButton.value) {
    updateOpen(false)
  }
}

function onSelect(item: PMenuItemProps) {
  if (props.type === 'single') {
    selectedItems.clear()
    selectedItems.add(item)
    onApply()
  }
  emits('select', item)
}

const noneItem = ref<HTMLElement | null>(null)
const selectAllItem = ref<HTMLElement | null>(null)

const { testIdAttrs } = useTestId()
</script>

<template>
  <PMenu
    v-bind="delegatedProps"
    :class="cn('max-h-60', props.class)"
    :open="open"
    :search-debounce="props.searchDebounce"
    :disable-search-filter="props.disableSearchFilter"
    @update:open="onOpenChange"
    @update:debounced-search="emits('update:debouncedSearch', $event)"
    @search="emits('search', $event)"
  >
    <template #trigger>
      <slot name="trigger" />
    </template>
    <template #content>
      <div v-bind="testIdAttrs">
        <div
          v-if="$slots['content-prepend']"
          class="px-3 py-2"
        >
          <slot name="content-prepend" />
        </div>
        <PMenuItem
          v-if="props.type === 'single' && props.hideFooter && props.clearable"
          id="none"
          ref="noneItem"
          :class="cn(props.type === 'single' && selectedItems.size === 0 ? 'bg-(--partner-fill-selected)' : '')"
          type="item"
          label="None"
          @select="onClear"
        />
        <PMenuItem
          v-if="props.type === 'multi' && !props.hideSelectAll"
          ref="selectAllItem"
          type="checkbox"
          :label="allSelected ? 'Deselect All' : 'Select All'"
          :model-value="selectAllState"
          prevent-close
          @update:model-value="onToggleAll"
        />
        <PMenuItem
          v-if="noneItem || selectAllItem"
          type="separator"
        />
        <PMenuItem 
          v-for="item in items" 
          v-bind="item"
          :key="item.label"
          v-scroll-into-view="props.scrollIntoView && selectedItems.has(item)"
          :data-selected="selectedItems.has(item) || undefined"
          :class="cn(props.type === 'single' && selectedItems.has(item) && !item.disabled ? 'bg-(--partner-fill-selected)' : '')" 
          :model-value="selectedItems.has(item)"
          :prevent-close="props.type === 'multi'"
          :type="item.type ?? (props.type === 'multi' ? 'checkbox' : 'item')"
          @update:model-value="onUpdateModelValue($event, item)" 
          @select="onSelect(item)"
        />
        <div
          v-if="$slots['content-append']"
          class="px-3 py-2"
        >
          <slot name="content-append" />
        </div>
      </div>
    </template>
    <template
      v-if="!props.hideFooter"
      #footer
    >
      <div class="flex justify-between gap-2">
        <PButton
          v-if="props.clearable"
          :disabled="selectedCount === 0 && (!props.selectedCountOverride || props.selectedCountOverride === 0)"
          variant="primary"
          appearance="text"
          @click="onClear"
        >
          Clear{{ ((selectedCount > 0 && props.type === 'multi') || (props.selectedCountOverride && props.selectedCountOverride > 0)) ? ` (${props.selectedCountOverride || selectedCount})` : '' }}
        </PButton>
        <PButton
          v-if="props.type === 'multi'"
          ref="applyButton"
          :disabled="props.required && selectedCount === 0"
          variant="primary"
          appearance="text"
          @click="onApply"
        >
          Apply
        </PButton>
      </div>
    </template>
  </PMenu>
</template>