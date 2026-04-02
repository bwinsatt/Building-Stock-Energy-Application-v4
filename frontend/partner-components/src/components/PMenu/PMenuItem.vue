<script setup lang="ts">
import '@/styles/global.css'
import { 
  computed,
  inject,
  ref,
  useSlots,
  type ComputedRef,
  type Ref,
  type VNode,
} from 'vue'
import { useVModel } from '@vueuse/core'
import {
  DropdownMenuCheckboxItem,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuPortal,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
} from './dropdown-menu'
import { PIcon } from '@/components/PIcon'
import { cn } from '@/lib/utils'
import type { Size } from '@/types/size'
import { useTestId } from '@/composables/useTestId'

export interface PMenuItemProps {
  id?: string
  label?: string
  description?: string
  modelValue?: string | boolean
  type?: 'label' | 'item' | 'group' | 'checkbox' | 'sub' | 'separator'
  disabled?: boolean
  icon?: string
  preventClose?: boolean
}

const props = withDefaults(defineProps<PMenuItemProps>(), {
  type: 'item',
  size: 'medium',
  preventClose: false,
})

export interface PMenuItemEmits {
(e: 'select', payload: MouseEvent): void
(e: 'update:modelValue', value: string | boolean): void
}

const emits = defineEmits<PMenuItemEmits>()

const modelValue = useVModel(props, 'modelValue', emits, {
  eventName: 'update:modelValue',
  passive: true,
  defaultValue: props.modelValue,
}) as ComputedRef<string | boolean>

const checkboxModelValue = computed({
  get: () => modelValue.value as boolean | 'indeterminate',
  set: (val) => emits('update:modelValue', val),
}) as ComputedRef<boolean | 'indeterminate'>

const parentSize = inject<Size>('size')

const sizeClass = computed(() => {
  switch (parentSize) {
    case 'small':
      return 'py-1'
    case 'large':
      return 'py-3'
    default:
      return 'py-2'
  }
}) as ComputedRef<string>

const itemClass = computed(() => cn('px-3', sizeClass.value, 'focus:bg-(--partner-inherit-hovered) data-[state=open]:bg-(--partner-inherit-hovered)'))


//--- Search and Visibility---
const menuSearch = inject<Ref<string>>('menuSearch', ref(''))

const slots = useSlots()

function getDefaultSlotVNodes(vnode: VNode): VNode[] {
  const { children } = vnode
  if (children && typeof children === 'object' && !Array.isArray(children) && typeof children.default === 'function') {
    return children.default() as VNode[]
  }
  return []
}

function extractLabels(vnodes: VNode[]): string[] {
  return vnodes.flatMap(vnode => [
    ...(vnode.props?.label ? [vnode.props.label] : []),
    ...extractLabels(getDefaultSlotVNodes(vnode)),
  ])
}

const childLabels = computed(() => extractLabels(slots.default?.({}) ?? []))

const isVisible = computed(() => {
  if (!menuSearch.value) return true
  const search = menuSearch.value.toLowerCase()
  if (props.label?.toLowerCase().includes(search)) return true
  return childLabels.value.some(l => l.toLowerCase().includes(search))
})
//--- End Search and Visibility---

const handleSelect = (event: MouseEvent) => {
  emits('select', event)
  if ( props.preventClose ) { event.preventDefault() }
}

const { testIdAttrs } = useTestId()
</script>

<template>
  <div
    ref="itemElement"
    v-bind="testIdAttrs"
    :data-has-icon="icon || undefined"
    class="partner-preflight data-[disabled]:text-(--partner-text-disabled)"
  >
    <DropdownMenuLabel
      v-if="type === 'label'"
      :id="id"
      :class="itemClass"
    >
      <slot name="label">
        {{ label }}
      </slot>
    </DropdownMenuLabel>
    <DropdownMenuItem
      v-else-if="type === 'item'"
      v-show="isVisible"
      :id="id"
      :class="itemClass"
      :disabled="disabled"
      :description="description"
      @select="handleSelect"
    >
      <div :class="cn('flex flex-row items-center gap-2', !icon && 'group-has-[>_[data-has-icon]]:pl-6')">
        <PIcon
          v-if="icon"
          :name="icon"
          size="small"
          data-left-icon
        />
        <slot>
          {{ label }}
        </slot>
        <PIcon
          v-if="modelValue"
          name="checkmark"
          size="small"
          :data-disabled="disabled ? true : undefined"
          class="ml-auto text-(--partner-action-active) data-[disabled]:text-(--partner-action-disabled)"
          data-right-icon
        />
      </div>
    </DropdownMenuItem>
    <DropdownMenuGroup
      v-else-if="type === 'group'"
      v-show="isVisible"
      :id="id"
      class="group"
    >
      <DropdownMenuLabel v-if="label">
        <slot name="label">
          {{ label }}
        </slot>
      </DropdownMenuLabel>
      <slot />
    </DropdownMenuGroup>
    <DropdownMenuCheckboxItem
      v-else-if="type === 'checkbox'"
      v-show="isVisible"
      :id="id"
      v-model="checkboxModelValue"
      :class="itemClass"
      :disabled="disabled"
      :description="description"
      @select="handleSelect($event as MouseEvent)"
    >
      <slot name="checkbox">
        {{ label }}
      </slot>
    </DropdownMenuCheckboxItem>
    <DropdownMenuSub
      v-else-if="type === 'sub'"
      :id="id"
    >
      <DropdownMenuSubTrigger
        v-show="isVisible"
        :class="itemClass"
      >
        <slot name="sub-trigger">
          {{ label }}
        </slot>
      </DropdownMenuSubTrigger>
      <DropdownMenuPortal>
        <DropdownMenuSubContent>
          <slot />
        </DropdownMenuSubContent>
      </DropdownMenuPortal>
    </DropdownMenuSub>
    <DropdownMenuSeparator
      v-else-if="type === 'separator'"
      :id="id"
    >
      <slot>
        {{ label }}
      </slot>
    </DropdownMenuSeparator>
  </div>
</template>