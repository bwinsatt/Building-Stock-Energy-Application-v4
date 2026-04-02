<script setup lang="ts">
import '@/styles/global.css'
import { ref, computed, watch, type Ref, type ComputedRef } from 'vue'
import { Calendar } from './calendar'
import { CalendarDate, isSameDay, fromDate, getLocalTimeZone, type DateValue } from '@internationalized/date'
import { DateTime } from 'luxon'
import { toDateTime, toDateValue } from '@/utils/datetime'
import { type PMenuItemProps } from '@/components/PMenu'
import { PSelect } from '@/components/PSelect'
import { cn } from '@/lib/utils'
import { useTestId } from '@/composables/useTestId'
import { PButton } from '@/components/PButton'

export type PCalendarProps = {
  modelValue?: DateTime,
  defaultValue?: DateTime,
  clearable?: boolean,
  disabled?: boolean,
  minValue?: DateTime,
  maxValue?: DateTime,
  monthFormat?: 'numeric' | '2-digit' | 'short' | 'long'
  yearRange?: number,
  years?: number[],
  locale?: string,
  unavailableDates?: DateTime[],
  isDateUnavailable?: (date: DateTime) => boolean,
}

const props = withDefaults(defineProps<PCalendarProps>(), {
  numberOfMonths: 1,
  monthFormat: 'short',
  yearRange: 20,
  locale: 'en-US',
})

export interface PCalendarEmits {
  (e: 'update:modelValue', value: DateTime | undefined): void
  (e: 'update:month', value: number): void
  (e: 'update:year', value: number): void
}

const emits = defineEmits<PCalendarEmits>()

const internalDate = ref(
  props.modelValue ? toDateValue(props.modelValue) : props.defaultValue ? toDateValue(props.defaultValue) : undefined
) as Ref<DateValue | undefined>

watch(() => props.modelValue, (newDate) => {
  const newVal = newDate ? toDateValue(newDate) : undefined
  if (!newVal && !internalDate.value) return
  if (newVal && internalDate.value && isSameDay(newVal, internalDate.value)) return
  internalDate.value = newVal
  if (newVal) placeholder.value = newVal
})

watch(internalDate, (val, oldVal) => {
  if (val === oldVal) return
  const newDateTime = val ? toDateTime(val) : undefined
  if (newDateTime && props.modelValue && newDateTime.hasSame(props.modelValue, 'day')) return
  emits('update:modelValue', newDateTime)
})

const placeholder = ref(
  props.modelValue ? toDateValue(props.modelValue) : props.defaultValue ? toDateValue(props.defaultValue) : fromDate(new Date(), getLocalTimeZone())
) as Ref<DateValue>

const months = computed(() => {
  const formatter = new Intl.DateTimeFormat(props.locale, { month: props.monthFormat })
  return Array.from({ length: 12 }, (_, i) => {
    const label = formatter.format(new Date(placeholder.value.year, i))
    return { id: String(i + 1), label, modelValue: String(i + 1) }
  })
}) as ComputedRef<PMenuItemProps[]>

const years = computed(() => {
  const yearList = props.years
    ?? Array.from({ length: props.yearRange }, (_, i) => {
      const currentYear = placeholder.value.year
      return currentYear - Math.floor(props.yearRange / 2) + i
    })

  return yearList.map(y => ({
    id: y.toString(),
    label: y.toString(),
    modelValue: y.toString(),
  }))
}) as ComputedRef<PMenuItemProps[]>

function onMonthApply(items: PMenuItemProps[]) {
  const month = parseInt(items[0].modelValue as string)
  placeholder.value = new CalendarDate(placeholder.value.year, month, 1)
  emits('update:month', month)
}
function onYearApply(items: PMenuItemProps[]) {
  const year = parseInt(items[0].modelValue as string)
  placeholder.value = new CalendarDate(year, placeholder.value.month, 1)
  emits('update:year', year)
}

const monthSelectWidth = computed(() => {
  switch (props.monthFormat) {
    case 'long': return 'w-28.5'
    case 'short': return 'w-18'
    default: return ''
  }
}) as ComputedRef<string>

const { testIdAttrs } = useTestId()

function onClear() {
  internalDate.value = undefined
}
</script>

<template>
  <div class="partner-preflight bg-(--partner-background-white) rounded-md border shadow-sm size-fit items-center justify-center">
    <Calendar
      v-model="internalDate"
      v-model:placeholder="placeholder"
      layout="month-and-year"
      :disabled="props.disabled"
      :min-value="props.minValue ? toDateValue(props.minValue) : undefined"
      :max-value="props.maxValue ? toDateValue(props.maxValue) : undefined"
      :is-date-unavailable="(date: DateValue) => (props.unavailableDates ?? []).some(d => isSameDay(toDateValue(d), date)) || (props.isDateUnavailable?.(toDateTime(date)) ?? false)"
      v-bind="{...testIdAttrs, ...$attrs}"
    >
      <template #heading>
        <div class="flex flex-row gap-1">
          <PSelect
            name="month"
            type="single"
            :model-value="months.find(m => m.modelValue === String(placeholder.month))?.label"
            :items="months"
            :disabled="props.disabled"
            :class="cn('text-center', monthSelectWidth)"
            size="small"
            @apply="onMonthApply"
          />
          <PSelect
            name="year"
            type="single"
            :model-value="years.find(y => y.modelValue === String(placeholder.year))?.label"
            :items="years"
            :disabled="props.disabled"
            class="text-center"
            size="small"
            @apply="onYearApply"
          />
        </div>
      </template>
    </Calendar>
    <slot name="footer">
      <div
        v-if="props.clearable"
        class="flex justify-between gap-2 pt-0 p-3"
      >
        <PButton
          variant="primary"
          appearance="text"
          :disabled="props.disabled"
          @click="onClear"
        >
          Clear
        </PButton>
      </div>
    </slot>
  </div>
</template>
