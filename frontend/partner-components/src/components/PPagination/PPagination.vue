<script setup lang="ts">
import '@/styles/global.css'
import type { HTMLAttributes } from 'vue'
import {
  PPaginationRoot,
  PPaginationContent,
  PPaginationEllipsis,
  PPaginationItem,
  PPaginationNext,
  PPaginationPrevious,
} from '.'
import { cn } from '@/lib/utils'
import { useTestId } from '@/composables/useTestId'

export interface PPaginationProps {
  class?: HTMLAttributes['class']
  size?: "small" | "medium"
  itemsPerPage: number
  totalPages: number
  currentPage: number
}

const props = defineProps<PPaginationProps>()

export interface PPaginationEmits {
  (e: 'update:page', page: number): void
}

const emits = defineEmits<PPaginationEmits>()

const { testIdAttrs } = useTestId()
</script>

<template>
  <div 
    :class="cn('partner-preflight flex flex-col gap-6', props.class)"
    v-bind="testIdAttrs"
  >
    <PPaginationRoot 
      v-slot="{ page }" 
      v-bind="testIdAttrs" 
      :items-per-page="props.itemsPerPage"
      :default-page="props.currentPage"
      :total="props.totalPages"
      @update:page="emits('update:page', $event)"
    >
      <PPaginationContent v-slot="{ items }">
        <PPaginationPrevious :size="props.size" />
        <template
          v-for="(item, index) in items"
          :key="index"
        >
          <PPaginationItem
            v-if="item.type === 'page'"
            :value="item.value"
            :is-active="item.value === page"
            :size="props.size"
          >
            {{ item.value }}
          </PPaginationItem>
          <PPaginationEllipsis
            v-else
            :key="item.type"
            :index="index"
            :size="props.size"
          >
            &#8230;
          </PPaginationEllipsis>
        </template>
        <PPaginationNext :size="props.size" />
      </PPaginationContent>
    </PPaginationRoot>
  </div>
</template>