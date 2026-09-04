<template>
  <div class="student-editor">
    <div v-if="showIdentity" class="student-editor__grid">
      <RegistrationTextField
        :id="fieldId('firstName')"
        v-model="student.firstName"
        label="First name"
        autocomplete="given-name"
        :error="fieldError('firstName')"
        required
      />
      <RegistrationTextField
        :id="fieldId('lastName')"
        v-model="student.lastName"
        label="Last name"
        autocomplete="family-name"
        :error="fieldError('lastName')"
        required
      />
      <RegistrationTextField
        :id="fieldId('email')"
        v-model="student.email"
        label="Student email"
        type="email"
        autocomplete="email"
        :error="fieldError('email')"
        required
      />
      <RegistrationTextField
        v-if="requireEmailConfirm"
        :id="fieldId('emailConfirm')"
        v-model="student.emailConfirm"
        label="Confirm student email"
        type="email"
        autocomplete="email"
        :error="fieldError('emailConfirm')"
        required
      />
    </div>

    <template v-if="showProfile">
      <div class="student-editor__grid">
        <RegistrationTextField
          :id="fieldId('school')"
          v-model="student.school"
          label="School"
          autocomplete="organization"
          :error="fieldError('school')"
          required
          wide
        />
        <label class="select-field">
          <span>Year level <span aria-hidden="true">*</span></span>
          <select
            :id="fieldId('yearLevel')"
            v-model="student.yearLevel"
            :aria-invalid="Boolean(fieldError('yearLevel'))"
            :aria-describedby="
              fieldError('yearLevel') ? `${fieldId('yearLevel')}-error` : undefined
            "
            required
          >
            <option value="" disabled>Select a year</option>
            <option v-for="year in ['9', '10', '11', '12']" :key="year" :value="year">
              Year {{ year }}
            </option>
          </select>
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
          :error="fieldError('country')"
          required
        />
        <RegistrationTextField
          :id="fieldId('state')"
          v-model="student.state"
          label="State or region"
          autocomplete="address-level1"
          optional
        />
      </div>

      <RegistrationInterestSelector
        :id="fieldId('interests')"
        v-model="student.interests"
        label="Student interests"
        description="Choose one or more areas that this student wants to explore."
        :error="fieldError('interests')"
      />

      <div v-if="showOptionalProfile" class="student-editor__extras">
        <div class="student-editor__grid">
          <label class="select-field">
            <span>Pronouns <small>Optional</small></span>
            <select :id="fieldId('pronouns')" v-model="student.pronouns">
              <option value="">Select pronouns</option>
              <option v-for="pronoun in PRONOUN_OPTIONS" :key="pronoun" :value="pronoun">
                {{ pronoun }}
              </option>
            </select>
          </label>
          <RegistrationTextField
            v-if="student.pronouns === 'Other'"
            :id="fieldId('pronounsOther')"
            v-model="student.pronounsOther"
            label="Your pronouns"
            :error="fieldError('pronounsOther')"
            required
          />
        </div>

        <div class="photo-field">
          <div class="photo-field__copy">
            <label :for="fieldId('profilePhoto')">Profile photo <small>Optional</small></label>
            <p>JPG, PNG, or WebP, up to 5 MB. The selected image stays in this browser preview.</p>
            <input
              :id="fieldId('profilePhoto')"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              :aria-invalid="Boolean(fieldError('profilePhoto'))"
              :aria-describedby="
                fieldError('profilePhoto') ? `${fieldId('profilePhoto')}-error` : undefined
              "
              @change="onPhotoChange"
            />
            <span
              v-if="fieldError('profilePhoto')"
              :id="`${fieldId('profilePhoto')}-error`"
              class="student-editor__error"
            >
              {{ fieldError('profilePhoto') }}
            </span>
          </div>
          <div v-if="previewUrl" class="photo-field__preview">
            <img :src="previewUrl" alt="Local profile photo preview" />
            <button type="button" @click="$emit('remove-photo')">Remove photo</button>
          </div>
        </div>
      </div>
    </template>

    <div v-if="showGuardian" class="guardian-editor">
      <label v-if="allowGuardianDefer" class="defer-control">
        <input v-model="student.guardianDeferred" type="checkbox" />
        <span>
          <strong>Guardian details will be added later</strong>
          <small>
            The student will need to supply them through their own action journey before consent can
            be completed.
          </small>
        </span>
      </label>

      <div v-if="!student.guardianDeferred" class="student-editor__grid">
        <RegistrationTextField
          :id="fieldId('guardian.firstName')"
          v-model="student.guardian.firstName"
          label="Guardian first name"
          :error="fieldError('guardian.firstName')"
          required
        />
        <RegistrationTextField
          :id="fieldId('guardian.lastName')"
          v-model="student.guardian.lastName"
          label="Guardian last name"
          :error="fieldError('guardian.lastName')"
          required
        />
        <RegistrationTextField
          :id="fieldId('guardian.email')"
          v-model="student.guardian.email"
          label="Guardian email"
          type="email"
          :error="fieldError('guardian.email')"
          required
        />
        <RegistrationTextField
          :id="fieldId('guardian.phone')"
          v-model="student.guardian.phone"
          label="Guardian phone"
          type="tel"
          optional
        />
        <label class="select-field">
          <span>Relationship <span aria-hidden="true">*</span></span>
          <select
            :id="fieldId('guardian.relationship')"
            v-model="student.guardian.relationship"
            :aria-invalid="Boolean(fieldError('guardian.relationship'))"
            :aria-describedby="
              fieldError('guardian.relationship')
                ? `${fieldId('guardian.relationship')}-error`
                : undefined
            "
            required
          >
            <option value="" disabled>Select a relationship</option>
            <option>Parent</option>
            <option>Legal guardian</option>
            <option>Other</option>
          </select>
          <span
            v-if="fieldError('guardian.relationship')"
            :id="`${fieldId('guardian.relationship')}-error`"
            class="student-editor__error"
          >
            {{ fieldError('guardian.relationship') }}
          </span>
        </label>
        <RegistrationTextField
          v-if="student.guardian.relationship === 'Other'"
          :id="fieldId('guardian.relationshipOther')"
          v-model="student.guardian.relationshipOther"
          label="Describe the relationship"
          :error="fieldError('guardian.relationshipOther')"
          required
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import RegistrationInterestSelector from '@/components/registration/RegistrationInterestSelector.vue'
import RegistrationTextField from '@/components/registration/RegistrationTextField.vue'
import { PRONOUN_OPTIONS, type StudentDetails } from '@/registration/registration'

const props = withDefaults(
  defineProps<{
    student: StudentDetails
    prefix: string
    section: 'identity' | 'profile' | 'guardian' | 'full' | 'teammate'
    errors: Record<string, string>
    requireEmailConfirm?: boolean
    allowGuardianDefer?: boolean
    showOptionalProfile?: boolean
    previewUrl?: string
  }>(),
  {
    requireEmailConfirm: false,
    allowGuardianDefer: false,
    showOptionalProfile: false,
    previewUrl: '',
  },
)

const emit = defineEmits<{
  'photo-selected': [file: File]
  'remove-photo': []
}>()

const showIdentity = computed(() => ['identity', 'full', 'teammate'].includes(props.section))
const showProfile = computed(() => ['profile', 'full'].includes(props.section))
const showGuardian = computed(() => ['guardian', 'full'].includes(props.section))
const safePrefix = computed(() => props.prefix.replace(/[^a-zA-Z0-9_-]/g, '-'))
const fieldId = (field: string) => `${safePrefix.value}-${field.replace(/\./g, '-')}`
const fieldError = (field: string) => props.errors[`${props.prefix}.${field}`]

const onPhotoChange = (event: Event) => {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (file) emit('photo-selected', file)
}
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

.student-editor__extras,
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
  display: flex;
  justify-content: space-between;
  color: var(--registration-ink);
  font-size: 0.9rem;
  font-weight: 750;
}

.select-field small {
  color: var(--registration-muted);
  font-size: 0.78rem;
  font-weight: 500;
}

select {
  width: 100%;
  min-height: 50px;
  padding: 0 42px 0 15px;
  border: 1px solid var(--registration-field-line);
  border-radius: 12px;
  outline: none;
  background: #fffefa;
  color: var(--registration-ink);
  font: inherit;
}

select:focus-visible {
  border-color: var(--registration-green);
  box-shadow: 0 0 0 3px rgba(8, 116, 90, 0.14);
}

select[aria-invalid='true'] {
  border-color: #a93732;
}

.student-editor__error {
  color: #982c27;
  font-size: 0.82rem;
  line-height: 1.35;
}

.photo-field {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
}

.photo-field__copy {
  display: grid;
  gap: 7px;
}

.photo-field__copy > label {
  color: var(--registration-ink);
  font-size: 0.9rem;
  font-weight: 750;
}

.photo-field__copy small {
  color: var(--registration-muted);
  font-weight: 500;
}

.photo-field__copy p {
  margin: 0;
  color: var(--registration-muted);
  font-size: 0.82rem;
  line-height: 1.45;
}

input[type='file'] {
  max-width: 100%;
  color: var(--registration-muted);
  font: inherit;
  font-size: 0.82rem;
}

input[type='file']::file-selector-button {
  min-height: 38px;
  margin-right: 10px;
  padding: 0 13px;
  border: 1px solid var(--registration-field-line);
  border-radius: 10px;
  background: #fffefa;
  color: var(--registration-green-dark);
  font: inherit;
  font-weight: 750;
  cursor: pointer;
}

.photo-field__preview {
  flex: 0 0 auto;
  display: grid;
  justify-items: center;
  gap: 6px;
}

.photo-field__preview img {
  width: 78px;
  height: 78px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid #d4e2dc;
}

.photo-field__preview button {
  padding: 3px;
  border: 0;
  background: transparent;
  color: var(--registration-green-dark);
  font: inherit;
  font-size: 0.78rem;
  font-weight: 750;
  text-decoration: underline;
  text-underline-offset: 3px;
  cursor: pointer;
}

.defer-control {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  cursor: pointer;
}

.defer-control input {
  width: 18px;
  height: 18px;
  margin-top: 2px;
  accent-color: var(--registration-green);
}

.defer-control span {
  display: grid;
  gap: 3px;
}

.defer-control strong {
  color: var(--registration-ink);
  font-size: 0.9rem;
}

.defer-control small {
  max-width: 64ch;
  color: var(--registration-muted);
  font-size: 0.82rem;
  line-height: 1.45;
}

@media (max-width: 620px) {
  .student-editor__grid {
    grid-template-columns: 1fr;
  }

  .photo-field {
    flex-direction: column;
  }
}
</style>
