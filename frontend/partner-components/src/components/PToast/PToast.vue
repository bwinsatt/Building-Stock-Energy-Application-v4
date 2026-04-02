<script lang="ts" setup>
import '@/styles/global.css'
import 'vue-sonner/style.css'
import type { ToasterProps } from "vue-sonner"
import { Toaster as Sonner } from "vue-sonner"
import { computed } from 'vue'
import { cn } from '@/lib/utils'

export type PToastProps = ToasterProps

const props = withDefaults(defineProps<PToastProps>(), {
  position: 'bottom-center',
  visibleToasts: 3,
  expand: false,
})

const mergedToastOptions = computed(() => ({
  ...props.toastOptions,
  classes: {
    ...props.toastOptions?.classes,
    toast: cn('group toast group-[.toaster]:shadow-md group-[.toaster]:w-full', props.toastOptions?.classes?.toast),
  },
}))
</script>

<template>
  <Sonner
    v-bind="props"
    class="partner-preflight toaster group"
    :toast-options="mergedToastOptions"
  />
</template>