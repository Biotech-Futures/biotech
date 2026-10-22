<template>
  <AppDateTimePicker
    mode="date"
    :model-value="modelValue"
    :placeholder="placeholder"
    :disabled="disabled"
    :clearable="clearable"
    :required="required"
    :min="min"
    :max="max"
    @update:model-value="(value: string) => emit('update:modelValue', value)"
    @change="(value: string) => emit('change', value)"
  />
</template>

<script setup lang="ts">
// A date alone, "YYYY-MM-DD": the app's date and time picker
// (AppDateTimePicker) with its month and no time. The page's classes,
// styles, data-test, id and aria-label pass through to it.
import AppDateTimePicker from '@/components/AppDateTimePicker.vue'

withDefaults(
  defineProps<{
    /** "YYYY-MM-DD", or empty for none yet. */
    modelValue?: string | null
    /** Shown while there's no date ("Select date" by default). */
    placeholder?: string
    disabled?: boolean
    /** A × in the box, to empty it (on by default). */
    clearable?: boolean
    /** A form with it can't be saved while it's empty. */
    required?: boolean
    /** The earliest and latest day it can be, "YYYY-MM-DD". */
    min?: string | null
    max?: string | null
  }>(),
  {
    modelValue: '',
    placeholder: undefined,
    disabled: false,
    clearable: true,
    required: false,
    min: undefined,
    max: undefined
  }
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
  /** After a date is picked or cleared, as an input's change event. */
  change: [value: string]
}>()
</script>
