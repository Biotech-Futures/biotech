<template>
  <div class="sydney-date-time">
    <!-- A Management date and time, entered apart, in Sydney's time whatever
         the computer's own: the date, then the time with Sydney's clock that
         day (AEDT or AEST). Each sits in the page's form as its other fields. -->
    <label class="sydney-date-time__field">
      <span>{{ dateLabel }}</span>
      <AppDatePicker
        class="sydney-date-time__date app-input app-input--compact"
        :model-value="date"
        :clearable="false"
        :required="required"
        :disabled="disabled"
        :min="min ? min.slice(0, 10) : undefined"
        :max="max ? max.slice(0, 10) : undefined"
        @update:model-value="setDate"
      />
    </label>
    <label class="sydney-date-time__field">
      <span>Time ({{ clock }})</span>
      <AppTimePicker
        class="sydney-date-time__time app-input app-input--compact"
        :model-value="time"
        :required="required || Boolean(date)"
        :disabled="disabled"
        :min="date && min && min.slice(0, 10) === date ? min.slice(11, 16) : undefined"
        :max="date && max && max.slice(0, 10) === date ? max.slice(11, 16) : undefined"
        @update:model-value="setTime"
      />
    </label>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import AppDatePicker from '@/components/AppDatePicker.vue'
import AppTimePicker from '@/components/AppTimePicker.vue'
import { sydneyClockOn, sydneyToday } from '@/utils/date'

const props = withDefaults(
  defineProps<{
    /** Sydney's "YYYY-MM-DDTHH:MM", or '' for none. */
    modelValue?: string | null
    /** "Opening Date": the date's label; the time's is Time, with Sydney's clock. */
    dateLabel: string
    /** The time shown before there's one, and a date picked starts at
     *  (23:59, the end of the day, unless the page gives another). */
    defaultTime?: string
    /** The earliest and latest it can be, as its value is written. */
    min?: string | null
    max?: string | null
    required?: boolean
    disabled?: boolean
  }>(),
  {
    modelValue: '',
    defaultTime: '23:59',
    min: undefined,
    max: undefined,
    required: false,
    disabled: false
  }
)

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

// The time shown with no date yet: the default, or one picked first. Emptied
// (Clear Dates, or the date's ×), it's the default again.
const pendingTime = ref(props.defaultTime)
watch(
  () => props.modelValue,
  (value) => {
    if (!value) pendingTime.value = props.defaultTime
  }
)

const date = computed(() => (props.modelValue || '').slice(0, 10))
const time = computed(() => (props.modelValue || '').slice(11, 16) || pendingTime.value)
// Sydney's clock on the day picked (today's until one is).
const clock = computed(() => sydneyClockOn(date.value || sydneyToday()).name)

// A date takes the time shown; emptied, there's no date and time at all.
const setDate = (value: string) => {
  emit('update:modelValue', value ? `${value}T${time.value}` : '')
}

// A time with no date yet waits for one.
const setTime = (value: string) => {
  const picked = value || props.defaultTime
  if (date.value) emit('update:modelValue', `${date.value}T${picked}`)
  else pendingTime.value = picked
}
</script>

<style scoped>
/* Its two fields sit in the page's form as its own fields do. */
.sydney-date-time {
  display: contents;
}

.sydney-date-time__field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.85rem;
  color: var(--teal);
}

/* The shared compact box (app-input), at its own width. */
.sydney-date-time__date,
.sydney-date-time__time {
  width: auto;
  max-width: none;
}
</style>
