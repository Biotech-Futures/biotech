<template>
  <div class="student-editor">
    <div v-if="showIdentity" class="student-editor__grid">
      <RegistrationTextField
        :id="fieldId('firstName')"
        v-model="student.firstName"
        label="First name"
        autocomplete="given-name"
        :error="fieldError('firstName')"
        :required="markRequired"
      />
      <RegistrationTextField
        :id="fieldId('lastName')"
        v-model="student.lastName"
        label="Last name"
        autocomplete="family-name"
        :error="fieldError('lastName')"
        :required="markRequired"
      />
      <RegistrationTextField
        :id="fieldId('email')"
        v-model="student.email"
        label="Student email"
        type="email"
        autocomplete="email"
        :error="fieldError('email')"
        :required="markRequired"
        wide
      />
    </div>

    <template v-if="showProfile">
      <div class="student-editor__grid">
        <RegistrationTextField
          :id="fieldId('school')"
          v-model="student.school"
          label="School"
          autocomplete="organization"
          :suggestions="schoolSuggestions"
          :error="fieldError('school')"
          :required="markRequired"
        />
        <label class="select-field">
          <span>Year level <span v-if="markRequired" class="required-mark" aria-hidden="true">*</span></span>
          <AppSelect
            :id="fieldId('yearLevel')"
            class="app-input"
            :model-value="student.yearLevel"
            :options="YEAR_LEVEL_OPTIONS"
            placeholder="Select a year"
            :aria-invalid="Boolean(fieldError('yearLevel'))"
            :aria-describedby="
              fieldError('yearLevel') ? `${fieldId('yearLevel')}-error` : undefined
            "
            :required="markRequired"
            @update:model-value="
              (value) => (student.yearLevel = String(value ?? '') as StudentDetails['yearLevel'])
            "
          />
          <span
            v-if="fieldError('yearLevel')"
            :id="`${fieldId('yearLevel')}-error`"
            class="student-editor__error"
          >
            {{ fieldError('yearLevel') }}
          </span>
        </label>
        <RegistrationTextField
          :id="fieldId('country')"
          v-model="student.country"
          label="Country"
          autocomplete="country-name"
          :options="countryOptions.length ? countryOptions : undefined"
          :placeholder="countryOptions.length ? 'Select a country' : undefined"
          :error="fieldError('country')"
          :required="markRequired"
        />
        <!-- In Australia, its State (required, a dropdown of its states and
             territories); elsewhere typed in (optional). -->
        <RegistrationTextField
          :id="fieldId('state')"
          v-model="student.state"
          :label="stateLabel()"
          autocomplete="address-level1"
          :options="stateOptions.length ? stateOptions : undefined"
          :suggestions="regionSuggestions"
          :placeholder="stateOptions.length ? 'Select a state' : undefined"
          :error="fieldError('state')"
          :required="markRequired && isAustralia(student.country)"
          :optional="!isAustralia(student.country)"
        />
      </div>

      <RegistrationInterestSelector
        v-if="showInterests"
        :id="fieldId('interests')"
        v-model="student.interests"
        label="Area(s) of Interest"
        :show-required="false"
        :error="fieldError('interests')"
      />

      <RegistrationProfileExtras
        v-if="showOptionalProfile"
        v-model:pronouns="student.pronouns"
        v-model:pronouns-other="student.pronounsOther"
        :prefix="prefix"
        :errors="errors"
        :preview-url="previewUrl"
        @photo-selected="emit('photo-selected', $event)"
        @remove-photo="emit('remove-photo')"
      />
    </template>

    <div v-if="showGuardian" class="guardian-editor">
      <label v-if="allowGuardianDefer" class="defer-control">
        <input v-model="provideGuardian" type="checkbox" />
        <span>
          <strong>Add guardian contact (optional)</strong>
          <small>
            If not provided now, the student will need to add these details before guardian
            permission can be requested.
          </small>
        </span>
      </label>

      <div v-if="!student.guardianDeferred" class="student-editor__grid">
        <RegistrationTextField
          :id="fieldId('guardian.firstName')"
          v-model="student.guardian.firstName"
          label="Guardian first name"
          :error="fieldError('guardian.firstName')"
          :required="markRequired"
        />
        <RegistrationTextField
          :id="fieldId('guardian.lastName')"
          v-model="student.guardian.lastName"
          label="Guardian last name"
          :error="fieldError('guardian.lastName')"
          :required="markRequired"
        />
        <RegistrationTextField
          :id="fieldId('guardian.email')"
          v-model="student.guardian.email"
          label="Guardian email"
          type="email"
          :error="fieldError('guardian.email')"
          :required="markRequired"
          wide
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'

import AppSelect, { type AppSelectOption } from '@/components/AppSelect.vue'
import RegistrationInterestSelector from '@/components/registration/RegistrationInterestSelector.vue'
import RegistrationProfileExtras from '@/components/registration/RegistrationProfileExtras.vue'
import RegistrationTextField from '@/components/registration/RegistrationTextField.vue'
import {
  isAustralia,
  stateLabel,
  type StudentDetails,
} from '@/registration/registration'
import { useCountryOptions, useStateOptions } from '@/registration/useLocationOptions'

const props = withDefaults(
  defineProps<{
    prefix: string
    section: 'identity' | 'profile' | 'guardian' | 'full' | 'teammate'
    errors: Record<string, string>
    allowGuardianDefer?: boolean
    showOptionalProfile?: boolean
    showInterests?: boolean
    previewUrl?: string
    /** Schools the others in their group gave, offered as theirs is typed. */
    schoolSuggestions?: string[]
    /** States the others in their group gave, for a typed state (outside
     *  Australia, whose states are a dropdown). */
    regionSuggestions?: string[]
  }>(),
  {
    allowGuardianDefer: false,
    showOptionalProfile: false,
    showInterests: true,
    previewUrl: '',
    schoolSuggestions: () => [],
    regionSuggestions: () => [],
  },
)

const emit = defineEmits<{
  'photo-selected': [file: File]
  'remove-photo': []
}>()
const student = defineModel<StudentDetails>('student', { required: true })

const YEAR_LEVEL_OPTIONS: AppSelectOption[] = ['9', '10', '11', '12'].map((year) => ({
  value: year,
  label: `Year ${year}`,
}))
// The countries, and in Australia its states, from the database, for dropdowns.
const countryOptions = useCountryOptions()
const stateOptions = useStateOptions(() => student.value.country)
// Another country: its state or region starts again (NSW isn't Algeria's).
// Only for the same student, and only from a country they'd picked: the
// first one picked (none to start) keeps what's there. The form can be
// handed another (a list's student removed), whose own state stays.
watch(
  () => [student.value, student.value.country] as const,
  ([current, country], [before, beforeCountry]) => {
    if (current === before && beforeCountry && country !== beforeCountry) current.state = ''
  },
)

const showIdentity = computed(() => ['identity', 'full', 'teammate'].includes(props.section))
// A group member (teammate) is asked for only once any of their details are
// given, so their fields carry no *.
const markRequired = computed(() => props.section !== 'teammate')
// A group member (teammate) gives their school, year and location too.
const showProfile = computed(() => ['profile', 'full', 'teammate'].includes(props.section))
const showGuardian = computed(
  () =>
    ['guardian', 'full'].includes(props.section) ||
    (props.section === 'teammate' && props.allowGuardianDefer),
)
const provideGuardian = computed({
  get: () => !student.value.guardianDeferred,
  set: (value: boolean) => {
    student.value.guardianDeferred = !value
  },
})
const safePrefix = computed(() => props.prefix.replace(/[^a-zA-Z0-9_-]/g, '-'))
const fieldId = (field: string) => `${safePrefix.value}-${field.replace(/\./g, '-')}`
const fieldError = (field: string) => props.errors[`${props.prefix}.${field}`]
</script>

<style scoped>
.student-editor {
  display: grid;
  gap: 30px;
}

.student-editor__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.guardian-editor {
  padding-top: 26px;
  display: grid;
  gap: 22px;
  border-top: 1px solid var(--registration-line);
}

.select-field {
  display: grid;
  align-content: start;
  gap: 7px;
}

.select-field > span {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  color: var(--registration-ink);
  font-size: 0.9rem;
  font-weight: 600;
}

.select-field small {
  color: var(--registration-muted);
  font-size: 0.78rem;
  font-weight: 500;
}

/* The shared box (app-input), as the text boxes beside it, in
   registration's colours. */
.app-select {
  border-color: var(--registration-field-line);
  outline: none;
  background: var(--white);
  color: var(--registration-ink);
}

.app-select:focus-within {
  border-color: var(--registration-green);
  box-shadow: 0 0 0 3px rgba(8, 116, 90, 0.14);
}

/* Its border and soft ring only: no outline. */
.select-field .app-select:has(.app-select__input:focus-visible) {
  outline: none;
}

.app-select:has([aria-invalid='true']) {
  border-color: #a93732;
}

.student-editor__error {
  color: #982c27;
  font-size: 0.82rem;
  line-height: 1.35;
}

.defer-control {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  cursor: pointer;
}

/* In rem, as its text is, so it stays centred on the heading's line at any
   text size: half that line (0.9rem at 1.6) less half the box. */
.defer-control input {
  flex: 0 0 auto;
  width: 1.125rem;
  height: 1.125rem;
  margin-top: calc((0.9rem * 1.6 - 1.125rem) / 2);
  accent-color: var(--registration-green);
}

.defer-control span {
  display: grid;
  gap: 3px;
}

.defer-control strong {
  color: var(--registration-ink);
  font-size: 0.9rem;
  line-height: 1.6;
}

.defer-control small {
  color: var(--registration-muted);
  font-size: 0.82rem;
  line-height: 1.45;
}

@media (max-width: 620px) {
  .student-editor__grid {
    grid-template-columns: 1fr;
  }
}
</style>
