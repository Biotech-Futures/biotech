<template>
  <!-- Pronouns and a profile photo, both optional: a student's on their
       profile step, and a supervisor's registering themselves. -->
  <div class="profile-extras">
    <div class="profile-extras__grid">
      <label class="select-field">
        <span>Pronouns <small>(Optional)</small></span>
        <AppSelect
          :id="fieldId('pronouns')"
          class="app-input"
          :model-value="pronouns"
          :options="PRONOUN_SELECT_OPTIONS"
          placeholder="Select pronouns"
          clearable
          @update:model-value="(value) => (pronouns = String(value ?? ''))"
        />
      </label>
      <RegistrationTextField
        v-if="pronouns === 'Other'"
        :id="fieldId('pronounsOther')"
        v-model="pronounsOther"
        label="Your pronouns"
        :error="fieldError('pronounsOther')"
        required
      />
    </div>

    <div class="photo-field">
      <div class="photo-field__copy">
        <label :for="fieldId('profilePhoto')">Profile photo <small>(Optional)</small></label>
        <p>
          JPG, PNG, or WebP, up to 5 MB. The image is uploaded when you submit registration.
        </p>
        <input
          :id="fieldId('profilePhoto')"
          type="file"
          accept="image/jpeg,image/png,image/webp"
          :aria-invalid="Boolean(fieldError('profilePhoto'))"
          :aria-describedby="fieldError('profilePhoto') ? `${fieldId('profilePhoto')}-error` : undefined"
          @change="onPhotoChange"
        />
        <span
          v-if="fieldError('profilePhoto')"
          :id="`${fieldId('profilePhoto')}-error`"
          class="profile-extras__error"
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

<script setup lang="ts">
import { computed } from 'vue'

import AppSelect from '@/components/AppSelect.vue'
import RegistrationTextField from '@/components/registration/RegistrationTextField.vue'
import { PRONOUN_SELECT_OPTIONS } from '@/utils/pronouns'

const props = withDefaults(
  defineProps<{
    /** Whose fields: their errors are under it, and their ids made from it. */
    prefix: string
    errors: Record<string, string>
    previewUrl?: string
  }>(),
  { previewUrl: '' },
)

const emit = defineEmits<{
  'photo-selected': [file: File]
  'remove-photo': []
}>()
const pronouns = defineModel<string>('pronouns', { required: true })
const pronounsOther = defineModel<string>('pronounsOther', { required: true })

const safePrefix = computed(() => props.prefix.replace(/[^a-zA-Z0-9_-]/g, '-'))
const fieldId = (field: string) => `${safePrefix.value}-${field}`
const fieldError = (field: string) => props.errors[`${props.prefix}.${field}`]

const onPhotoChange = (event: Event) => {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (file) emit('photo-selected', file)
}
</script>

<style scoped>
.profile-extras {
  padding-top: 26px;
  display: grid;
  gap: 22px;
  border-top: 1px solid var(--registration-line);
}

.profile-extras__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
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

.profile-extras__error {
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
  font-weight: 600;
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
  min-height: 44px;
  margin-right: 10px;
  padding: 0 13px;
  border: 1px solid var(--registration-field-line);
  border-radius: 4px;
  background: var(--white);
  color: var(--registration-green-dark);
  font: inherit;
  font-weight: 500;
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

@media (max-width: 620px) {
  .profile-extras__grid {
    grid-template-columns: 1fr;
  }

  .photo-field {
    flex-direction: column;
  }
}
</style>
