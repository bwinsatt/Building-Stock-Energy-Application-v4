<script setup lang="ts">
import '@/styles/global.css'
import { ref, provide, watch, computed, type HTMLAttributes } from 'vue'
import { refDebounced } from "@vueuse/core"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuPortal,
  DropdownMenuTrigger,
  DropdownMenuLabel,
} from './dropdown-menu'
import { PSearchBar } from '@/components/PSearchBar'
import { cn } from '@/lib/utils'
import type { Size } from '@/types/size'
import { useTestId } from '@/composables/useTestId'

export interface PMenuProps {
  class?: HTMLAttributes['class']
  contentClass?: HTMLAttributes['class']
  size?: Size
  align?: 'start' | 'center' | 'end'
  defaultOpen?: boolean
  open?: boolean
  modal?: boolean
  label?: string
  disabled?: boolean
  searchable?: boolean
  disableSearchFilter?: boolean
  searchDebounce?: number
}

const props = withDefaults(defineProps<PMenuProps>(), {
  align: 'start',
  size: 'medium',
})

export interface PMenuEmits {
  (e: 'update:open', value: boolean): void
  (e: 'update:debouncedSearch', value: string): void
  (e: 'search', value: string): void
}

const emits = defineEmits<PMenuEmits>()

provide('size', props.size)

const open = ref(props.defaultOpen ?? false)

watch(() => props.open, (value) => {
  if (value !== undefined) open.value = value
})

function onOpenChange(value: boolean) {
  open.value = value
  emits('update:open', value)
}

const menuSearch = ref('')
const debouncedMenuSearch = refDebounced(menuSearch, props.searchDebounce ?? 300)
const providedSearch = computed(() => props.disableSearchFilter ? '' : debouncedMenuSearch.value)
provide('menuSearch', providedSearch)

const { testIdAttrs } = useTestId()
</script>

<template>
  <DropdownMenu
    :open="open"
    :modal="props.modal"
    class="partner-preflight"
    @update:open="onOpenChange"
  >
    <DropdownMenuTrigger
      as-child
      :disabled="props.disabled"
    >
      <slot name="trigger" />
    </DropdownMenuTrigger>

    <DropdownMenuPortal>
      <DropdownMenuContent
        :class="cn('partner-preflight z-(--partner-z-dropdown) p-0 border-(--partner-border-light)', props.contentClass)"
        :align="props.align"
      >
        <div v-bind="testIdAttrs">
          <DropdownMenuLabel v-if="props.label">
            <slot name="label">
              {{ props.label }}
            </slot>
          </DropdownMenuLabel>
          <div class="flex flex-col gap-2">
            <slot name="header">
              <PSearchBar
                v-if="props.searchable"
                v-model="menuSearch"
                hide-search-button
                class="p-2"
                :debounce="props.searchDebounce"
                @keydown.stop
                @update:debounced-value="emits('update:debouncedSearch', $event)"
                @search="emits('search', $event)"
              />
            </slot>
            <div :class="cn('group w-full overflow-x-hidden overflow-y-auto partner-scrollbar', props.class)">
              <slot
                default
                name="content"
              />
            </div>
            <div
              v-if="$slots.footer"
              class="p-2"
            >
              <slot name="footer" />
            </div>
          </div>
        </div>
      </DropdownMenuContent>
    </DropdownMenuPortal>
  </DropdownMenu>
</template>
