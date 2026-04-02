<script setup lang="ts">
import '@/styles/global.css'
import { ref, watch, computed, type Ref, type HTMLAttributes } from 'vue'
import { isSameDay, type DateValue} from '@internationalized/date'
import { DateTime } from 'luxon'
import { toDateValue, toDateTime } from '@/utils/datetime'
import {
  // DatePickerAnchor,
  // DatePickerArrow,
  // DatePickerCalendar,
  // DatePickerCell,
  // DatePickerCellTrigger,
  // DatePickerClose,
  DatePickerContent,
  DatePickerField,
  // DatePickerGrid,
  // DatePickerGridBody,
  // DatePickerGridHead,
  // DatePickerGridRow,
  // DatePickerHeadCell,
  // DatePickerHeader,
  // DatePickerHeading,
  DatePickerInput,
  // DatePickerNext,
  // DatePickerPrev,
  DatePickerRoot,
  DatePickerTrigger,
} from 'reka-ui'
import { cn } from '@/lib/utils'
import { PInputWrapper } from '@/components/PInputWrapper'
import { PIcon } from '@/components/PIcon'
import { PCalendar } from '@/components/PCalendar'
import { useInputStyles } from '@/composables/useInputStyles'
import type { Size } from '@/types/size'
import { useTestId } from '@/composables/useTestId'
import type { PCalendarProps } from '@/components/PCalendar'

defineOptions({ inheritAttrs: false })

export interface PDateInputProps {
  class?: HTMLAttributes["class"]
  id?: string
  label?: string
  size?: Size
  disabled?: boolean
  required?: boolean
  error?: boolean
  errorText?: string
  helperText?: string
  modelValue?: DateTime
  defaultValue?: DateTime
  locale?: string
  calendarProps?: Omit<PCalendarProps, 'modelValue' | 'defaultValue'>
}

const props = defineProps<PDateInputProps>()

export interface PDateInputEmits {
  (e: "update:modelValue", payload: DateTime | undefined): void
}

const emits = defineEmits<PDateInputEmits>()

const internalDate = ref(
  props.modelValue ? toDateValue(props.modelValue) : props.defaultValue ? toDateValue(props.defaultValue) : undefined
) as Ref<DateValue | undefined>

watch(() => props.modelValue, (newVal) => {
  const newDateVal = newVal ? toDateValue(newVal) : undefined
  if (!newDateVal && !internalDate.value) return
  if (newDateVal && internalDate.value && isSameDay(newDateVal, internalDate.value)) return
  internalDate.value = newDateVal
})

watch(internalDate, (val, oldVal) => {
  if (val === oldVal) return
  const newDateTime = val ? toDateTime(val) : undefined
  if (newDateTime && props.modelValue && newDateTime.hasSame(props.modelValue, 'day')) return
  emits('update:modelValue', newDateTime)
})

const internalDateTime = computed({
  get: () => internalDate.value ? toDateTime(internalDate.value) : undefined,
  set: (val: DateTime | undefined) => {
    if (val) internalDate.value = toDateValue(val)
    else internalDate.value = undefined
  },
})

const { inputClass } = useInputStyles(props)

function formatSegment(part: string, value: string): string {
  value = value.toUpperCase()
  if (part === 'literal' || part === 'year') return value
  return value.padStart(2, '0')
}

function placeholderClass(value: string): string {
  return isNaN(Number(value)) ? 'text-partner-placeholder' : ''
}

function isDateUnavailable(date: DateValue): boolean {
  return props.calendarProps?.unavailableDates?.some(d => isSameDay(toDateValue(d), date))
  || (props.calendarProps?.isDateUnavailable?.(toDateTime(date)) ?? false)
}

const { testIdAttrs } = useTestId()
</script>

<template>
  <PInputWrapper v-bind="props">
    <DatePickerRoot
      :id="props.id"
      v-model="internalDate"
      granularity="day"
      :min-value="props.calendarProps?.minValue ? toDateValue(props.calendarProps.minValue) : undefined"
      :max-value="props.calendarProps?.maxValue ? toDateValue(props.calendarProps.maxValue) : undefined"
      :is-date-unavailable="isDateUnavailable"
      :disabled="props.disabled"
      :required="props.required"
      :locale="props.locale"
    >
      <DatePickerField
        v-slot="{ segments }"
        :class="cn('flex select-none items-center text-center justify-between data-[invalid]:border-(--partner-error-main)', inputClass, props.class)"
        v-bind="{...testIdAttrs, ...$attrs}"
      >
        <div class="flex items-center">
          <template
            v-for="item, index in segments"
            :key="`${item.part}-${index}`"
          >
            <DatePickerInput
              v-if="item.part === 'literal'"
              :part="item.part"
              :class="placeholderClass(segments[index-1]?.value)"
            >
              {{ formatSegment(item.part, item.value) }}
            </DatePickerInput>
            <DatePickerInput
              v-else
              :part="item.part"
              :class="cn('rounded-none px-0.5 focus:outline-none focus:shadow-[0_2px_0_0_var(--partner-border-active)] data-[placeholder]:text-partner-placeholder', placeholderClass(item.value))"
            >
              {{ formatSegment(item.part, item.value) }}
            </DatePickerInput>
          </template>
        </div>

        <DatePickerTrigger class="rounded-sm focus:ring-2 focus:ring-(--partner-border-active)">
          <PIcon
            name="calendar"
          />
        </DatePickerTrigger>
      </DatePickerField>

      <DatePickerContent
        :side-offset="4"
        class="z-(--partner-z-popover)"
      >
        <PCalendar
          v-model="internalDateTime"
          :clearable="true"
          v-bind="props.calendarProps"
        />
      </DatePickerContent>
    </DatePickerRoot>
  </PInputWrapper>
</template>