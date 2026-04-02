<script setup lang="ts">
import '@/styles/global.css'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from './dialog'
import type { DialogRootEmits, DialogRootProps } from "reka-ui"
import { useForwardPropsEmits } from "reka-ui"
import { PTypography } from '@/components/PTypography'
import { cn } from '@/lib/utils'
import { computed, useSlots, type HTMLAttributes } from 'vue'

export interface PDialogProps {
  class?: HTMLAttributes["class"]
  title?: string
  description?: string
  defaultOpen?: boolean
  open?: boolean
  modal?: boolean
  hideCloseButton?: boolean
  disableCloseOnEscape?: boolean
  disableCloseOnInteractOutside?: boolean
}
const props = defineProps<PDialogProps & DialogRootProps>()

export type PDialogEmits = DialogRootEmits
const emits = defineEmits<DialogRootEmits>()

const forwarded = useForwardPropsEmits(props, emits)

const hasTitle = computed(() => props.title || useSlots().title)
const hasDescription = computed(() => props.description || useSlots().description)
const hasHeader = computed(() => hasTitle.value || hasDescription.value)
</script>

<template>
  <Dialog
    v-bind="forwarded"
    :class="cn('partner-preflight')"
  >
    <DialogTrigger>
      <slot name="trigger" />
    </DialogTrigger>
    <DialogContent
      :class="cn('partner-preflight p-0 rounded-md sm:rounded-md shadow-md', props.class)"
      :hide-close-button="props.hideCloseButton"
      @escape-key-down="(event) => {
        if (props.disableCloseOnEscape) {
          event.preventDefault()
        }
      }"
      @pointer-down-outside="(event) => {
        if (props.disableCloseOnInteractOutside) {
          event.preventDefault()
        }
      }"
    >
      <div class="p-6">
        <DialogHeader
          v-if="hasHeader"
          :class="cn('gap-y-3')"
        >
          <DialogTitle v-if="hasTitle">
            <PTypography variant="h5">
              <slot name="title">
                {{ props.title }}
              </slot>
            </PTypography>
          </DialogTitle>
          <DialogDescription v-if="hasDescription">
            <PTypography variant="body1">
              <slot name="description">
                {{ props.description }}
              </slot>
            </PTypography>
          </DialogDescription>
        </DialogHeader>
        <div :class="cn(!props.hideCloseButton ? 'pt-6' : '')">
          <slot name="content">
            <slot />
          </slot>
        </div>
      </div>
      <DialogFooter
        v-if="$slots.footer"
        :class="cn('border-t border-(--partner-border-light) px-6 py-4')"
      >
        <slot name="footer" />
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
