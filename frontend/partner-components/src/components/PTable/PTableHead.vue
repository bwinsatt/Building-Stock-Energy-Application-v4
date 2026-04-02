<script setup lang="ts">
import '@/styles/global.css'
import type { HTMLAttributes, ComputedRef } from 'vue'
import { computed, inject, ref, watch, onBeforeUnmount } from 'vue'
import { TableHead } from '@/components/shadcn/ui/table'
import { useTestId } from '@/composables/useTestId'
import { cn } from '@/lib/utils'
import { PIcon } from '@/components/PIcon'
import { PTypography } from '@/components/PTypography'
import { PCheckbox, type CheckedState } from '@/components/PCheckbox'
import type { Size } from '@/types/size'
import { PButton, type PButtonProps } from '@/components/PButton'

type SortDirection = 'asc' | 'desc' | undefined

export interface PTableHeadEmits {
  (e: 'sortChanged', sortDirection: SortDirection): void
  (e: 'filterClicked', rect: DOMRect): void
  (e: 'selectChanged', value: CheckedState): void
  (e: 'expandClicked', expanded: boolean): void
}

export interface PTableHeadProps {
  class?: HTMLAttributes['class']
  size?: Size
  sortable?: boolean
  sortDirection?: SortDirection
  filterable?: boolean
  filtered?: boolean
  selectable?: boolean
  selected?: CheckedState | 'true' | 'false'
  expandable?: boolean
  expanded?: boolean
}

const props = defineProps<PTableHeadProps>()

const injectedSize = inject<ComputedRef<Size>>('headerSize')
const effectiveSize = computed(() => props.size ?? injectedSize?.value ?? 'medium') as ComputedRef<Size>

const emits = defineEmits<PTableHeadEmits>()

const sortIcon = computed(() => {
  switch (sortDirection.value) {
    case 'asc':
      return 'caret-sort-up'
    case 'desc':
      return 'caret-sort-down'
    default:
      return 'caret-sort'
  }
}) as ComputedRef<string>

const clickableClass = computed(() => {
  return props.sortable? 'cursor-pointer hover:bg-(--partner-inherit-hovered)' : ''
})

const expandIcon = computed(() => {
  return expanded.value ? 'chevron-down' : 'chevron-right'
}) as ComputedRef<string>

const dividerClass = computed(() => {
  return props.expandable || props.selectable ? '' : 'partner-th-divider'
}) as ComputedRef<string>

const widthClass = computed(() => {
  return props.expandable || props.selectable ? 'pr-0 w-10' : ''
}) as ComputedRef<string>

const sizeClass = computed(() => {
  switch (effectiveSize.value) {
    case 'small':
      return 'py-2'
    case 'medium':
    case 'large':
    default:
      return 'py-3'
  }
}) as ComputedRef<string>

const buttonProps: PButtonProps = {
  variant: 'neutral',
  appearance: 'text',
  iconButton: true,
  size: 'small',
}

const filterButtonProps = computed(() => {
  return {
    ...buttonProps,
    icon: props.filtered ? 'filter-applied' : 'filter',
    'data-testid': 'filter-icon',
    class: '[&_path#dot]:fill-(--partner-primary-light)',
    onClick: (e: MouseEvent) => { e.stopPropagation(); handleFilterClick() },
  }
}) as ComputedRef<PButtonProps>

const sortDirection = ref<SortDirection>(props.sortDirection)

watch(() => props.sortDirection, (newVal) => {
  sortDirection.value = newVal
})

const registerSortReset = inject<((fn: () => void) => () => void) | undefined>('registerSortReset', undefined)
const resetOtherSorts = inject<((except: () => void) => void) | undefined>('resetOtherSorts', undefined)

const resetSort = () => {
  sortDirection.value = undefined
}

// Only register if this head actually has sortDirection defined
if (props.sortable && registerSortReset) {
  const unregister = registerSortReset(resetSort)
  onBeforeUnmount(unregister)
}

const toggleSortDirection = () => {
  if (!sortDirection.value) {
    sortDirection.value = 'asc'
  } else if (sortDirection.value === 'asc') {
    sortDirection.value = 'desc'
  } else {
    sortDirection.value = undefined
  }
}

const handleSortClick = () => {
  resetOtherSorts?.(resetSort)
  toggleSortDirection()
  emits('sortChanged', sortDirection.value)
}

const filterButtonRef = ref<InstanceType<typeof PButton>>()

const handleFilterClick = () => {
  const buttonEl = filterButtonRef.value?.$el
  const rect = buttonEl?.getBoundingClientRect()
  emits('filterClicked', rect)
}

const handleSelectChanged = (value: CheckedState) => {
  emits('selectChanged', value)
}

const expanded = ref(props.expanded ?? false)

watch(() => props.expanded, (newVal) => {
  expanded.value = newVal
})

const toggleExpand = () => {
  expanded.value = !expanded.value
}

const handleExpandClick = () => {
  toggleExpand()
  emits('expandClicked', expanded.value)
}

const { testIdAttrs } = useTestId()
</script>

<template>
  <TableHead
    :class="cn('partner-preflight relative px-3', clickableClass, sizeClass, dividerClass, widthClass, props.class)"
    v-bind="testIdAttrs"
    :data-sort-direction="props.sortable ? sortDirection : undefined"
    :data-expanded="props.expandable ? expanded : undefined"
    @click="handleSortClick"
  >
    <div class="flex items-center min-w-0 flex-1">
      <div
        v-if="expandable || selectable"
        class="flex items-center flex-shrink-0"
      >
        <PButton 
          v-if="expandable"
          v-bind="buttonProps"
          :icon="expandIcon" 
          data-testid="expand-icon" 
          @click.stop="handleExpandClick"
        />
        <PCheckbox
          v-if="selectable"
          class="py-0"
          data-testid="select-checkbox"
          :checked="props.selected === true || props.selected === 'true'"
          :indeterminate="props.selected === 'indeterminate'"
          @changed="handleSelectChanged"
          @click.stop
        />
      </div>
      <PTypography
        variant="buttonMedium"
        component="span"
        truncate
        class="!text-(--partner-text-primary)"
      >
        <slot />
      </PTypography>
      <div
        v-if="sortable"
        class="flex items-center flex-shrink-0 select-none ml-1"
        data-testid="sort-icon"
      >
        <PIcon
          name="caret-sort"
          size="small"
          color="var(--partner-action-disabled)"
        />
        <PIcon
          :name="sortIcon"
          size="small"
          color="var(--partner-action-enabled)"
          class="absolute z-1"
        />
      </div>
      <div
        v-if="filterable"
        class="flex items-center flex-shrink-0 ml-auto pl-1 select-none"
      >
        <slot
          name="filterButton"
          v-bind="filterButtonProps"
        >
          <PButton 
            ref="filterButtonRef"
            v-bind="filterButtonProps"
          />
        </slot>
      </div>
    </div>
  </TableHead>
</template>

<style scoped>
  .partner-th-divider:not(:last-child)::after {
    content: '';
    position: absolute;
    right: 0;
    top: 50%;
    transform: translateY(-50%);
    height: 50%;
    width: 1px;
    background-color: var(--partner-border-disabled);
  }
  </style>