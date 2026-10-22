<template>
  <AppDateTimePicker
    mode="time"
    :model-value="modelValue"
    :placeholder="placeholder"
    :disabled="disabled"
    :clearable="clearable"
    :required="required"
    :min="min"
    :max="max"
    :step="step"
    :size="size"
    @update:model-value="(value: string) => emit('update:modelValue', value)"
    @change="(value: string) => emit('change', value)"
  />
</template>

<script setup lang="ts">
// A time of day alone, "HH:MM" in 24 hours: the app's date and time picker
// (AppDateTimePicker) with its hours and minutes and no month. The page's
// classes, styles, data-test and aria-label pass through to it.
import AppDateTimePicker from '@/components/AppDateTimePicker.vue'

withDefaults(
  defineProps<{
    /** "HH:MM", or empty for none yet. */
    modelValue?: string | null
    /** Shown while there's no time ("--:--" by default). */
    placeholder?: string
    disabled?: boolean
    /** A × in the box, to empty it. */
    clearable?: boolean
    /** A form with it can't be saved while it's empty. */
    required?: boolean
    /** The earliest and latest time it can be, "HH:MM". */
    min?: string | null
    max?: string | null
    /** The minutes offered, in steps of this many (AppDateTimePicker's
     *  MINUTE_STEPS by default: every 5). */
    step?: number
    /** Small, as tall as a select (the default); large, as tall as the
     *  page's text boxes beside it. */
    size?: 'small' | 'large'
  }>(),
  {
    modelValue: '',
    placeholder: undefined,
    disabled: false,
    clearable: false,
    required: false,
    min: undefined,
    max: undefined,
    step: undefined,
    size: 'small'
  }
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
  /** After a time is picked or cleared, as an input's change event. */
  change: [value: string]
}>()
</script>
