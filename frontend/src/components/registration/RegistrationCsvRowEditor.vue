<template>
  <div class="csv-fields">
    <RegistrationTextField
      v-for="field in fields"
      :id="`csv-row-${row.rowNumber}-${field.key}`"
      :key="field.key"
      :model-value="row.values[field.key] || ''"
      :label="field.label"
      :hint="field.hint"
      :type="excluded ? 'text' : field.type || 'text'"
      :required="!excluded && isRequired(field)"
      :optional="!isRequired(field)"
      :error="errors[field.key]"
      @update:model-value="updateField(field.key, $event)"
    />
  </div>
</template>

<script setup lang="ts">
import RegistrationTextField from './RegistrationTextField.vue'
import type { CsvHeader, CsvRow } from '@/registration/registration'

const props = withDefaults(
  defineProps<{
    row: CsvRow
    excluded?: boolean
    errors?: Partial<Record<CsvHeader, string>>
  }>(),
  { excluded: false, errors: () => ({}) },
)

const emit = defineEmits<{ 'update:values': [values: CsvRow['values']] }>()
const updateField = (field: CsvHeader, value: string) =>
  emit('update:values', { ...props.row.values, [field]: value })

const availableFields: Array<{
  key: CsvHeader
  label: string
  required?: boolean
  type?: string
  hint?: string
}> = [
  { key: 'first_name', label: 'First name', required: true },
  { key: 'last_name', label: 'Last name', required: true },
  { key: 'email', label: 'Student email', type: 'email', required: true },
  { key: 'school', label: 'School', required: true },
  { key: 'year_level', label: 'Year level', required: true, hint: '9, 10, 11, or 12.' },
  { key: 'country', label: 'Country', required: true },
  { key: 'state', label: 'State or region', hint: 'Required for Australian students.' },
  {
    key: 'interests',
    label: 'Areas of Interest',
    required: true,
    hint: 'Separate multiple interests with commas.',
  },
  { key: 'guardian_first_name', label: 'Guardian first name' },
  { key: 'guardian_last_name', label: 'Guardian last name' },
  { key: 'guardian_email', label: 'Guardian email', type: 'email' },
  {
    key: 'guardian_relationship',
    label: 'Guardian relationship',
    hint: 'Parent, Legal guardian, or Other.',
  },
  {
    key: 'guardian_relationship_other',
    label: 'Other guardian relationship',
    hint: 'Required when the relationship is Other.',
  },
  {
    key: 'grouping_preference',
    label: 'Legacy grouping preference',
    hint: 'Optional legacy CSV value: school_only or cross_school. Leave blank if not supplied.',
  },
]
const showLegacyGrouping = Boolean(
  props.row.values.grouping_preference || props.errors.grouping_preference,
)
const fields = availableFields.filter(
  (field) => field.key !== 'grouping_preference' || showLegacyGrouping,
)
const isRequired = (field: (typeof availableFields)[number]) => {
  if (field.key === 'state')
    return (props.row.values.country || '').trim().toLowerCase() === 'australia'
  if (field.key === 'guardian_relationship_other')
    return props.row.values.guardian_relationship === 'Other'
  return Boolean(field.required)
}
</script>

<style scoped>
.csv-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
}

@media (max-width: 620px) {
  .csv-fields {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
