<template>
  <!-- A file's row, edited on Register one student's own form: its fields,
       dropdowns, Areas of Interest and optional guardian contact. -->
  <RegistrationStudentEditor
    v-model:student="student"
    :prefix="prefix"
    section="full"
    :errors="studentErrors"
    allow-guardian-defer
  />
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import RegistrationStudentEditor from './RegistrationStudentEditor.vue'
import {
  createStudent,
  interestOption,
  parseRegistrationInterests,
  type CsvHeader,
  type CsvRow,
  type StudentDetails,
} from '@/registration/registration'

const props = withDefaults(
  defineProps<{
    row: CsvRow
    errors?: Partial<Record<CsvHeader, string>>
  }>(),
  { errors: () => ({}) },
)

const emit = defineEmits<{ 'update:values': [values: CsvRow['values']] }>()

// Each column's field on the student form.
const FIELDS: Record<CsvHeader, string> = {
  first_name: 'firstName',
  last_name: 'lastName',
  email: 'email',
  school: 'school',
  year_level: 'yearLevel',
  country: 'country',
  state: 'state',
  interests: 'interests',
  guardian_first_name: 'guardian.firstName',
  guardian_last_name: 'guardian.lastName',
  guardian_email: 'guardian.email',
}

// "csv-row-3": the form's fields are "csv-row-3-firstName" and so on.
const prefix = computed(() => `csv-row-${props.row.rowNumber}`)

// The row as a student. Its guardian is left for later when none of its
// guardian columns is filled in.
const fromRow = (values: CsvRow['values']): StudentDetails => {
  const student = createStudent({ deferGuardian: true })
  return {
    ...student,
    firstName: values.first_name,
    lastName: values.last_name,
    email: values.email,
    emailConfirm: values.email,
    school: values.school,
    yearLevel: values.year_level as StudentDetails['yearLevel'],
    country: values.country,
    state: values.state,
    // As the options name them; any that aren't options stay (and in error).
    interests: parseRegistrationInterests(values.interests).map(
      (interest) => interestOption(interest) ?? interest,
    ),
    guardian: {
      ...student.guardian,
      firstName: values.guardian_first_name,
      lastName: values.guardian_last_name,
      email: values.guardian_email,
    },
    guardianDeferred: ![
      values.guardian_first_name,
      values.guardian_last_name,
      values.guardian_email,
    ].some(Boolean),
  }
}

// One student per row: the page keys this editor by the row's number.
const student = ref<StudentDetails>(fromRow(props.row.values))

// An interest chosen or cleared: any the file had that aren't options go.
watch(
  () => [...student.value.interests],
  (now, before) => {
    if (now.length !== before.length && now.some((interest) => !interestOption(interest)))
      student.value.interests = now.filter((interest) => interestOption(interest))
  },
)

// Back to the row as it's edited; no guardian when it's left for later.
watch(
  student,
  (edited) => {
    const guardian = edited.guardianDeferred
      ? { firstName: '', lastName: '', email: '' }
      : edited.guardian
    emit('update:values', {
      ...props.row.values,
      first_name: edited.firstName,
      last_name: edited.lastName,
      email: edited.email,
      school: edited.school,
      year_level: edited.yearLevel,
      country: edited.country,
      state: edited.state,
      interests: edited.interests.join(', '),
      guardian_first_name: guardian.firstName,
      guardian_last_name: guardian.lastName,
      guardian_email: guardian.email,
    })
  },
  { deep: true },
)

// The row's problems on the form's fields.
const studentErrors = computed(() =>
  Object.fromEntries(
    Object.entries(props.errors)
      .filter(([, message]) => message)
      .map(([column, message]) => [`${prefix.value}.${FIELDS[column as CsvHeader]}`, message!]),
  ),
)
</script>
