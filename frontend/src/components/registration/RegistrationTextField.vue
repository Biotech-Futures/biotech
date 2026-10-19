<template>
  <label class="registration-field" :class="{ 'registration-field--wide': wide }">
    <span :id="`${id}-label`" class="registration-field__label">
      {{ label }}
      <small v-if="optional">(Optional)</small>
      <span v-else-if="required" class="required-mark" aria-hidden="true">*</span>
    </span>
    <textarea
      v-if="multiline"
      :id="id"
      :value="modelValue"
      :rows="rows"
      :placeholder="placeholder"
      :aria-invalid="Boolean(error)"
      :aria-labelledby="`${id}-label`"
      :aria-describedby="describedBy"
      :required="required"
      @input="$emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
    ></textarea>
    <!-- Given options (e.g. Australia's states), a dropdown of them instead. -->
    <AppSelect
      v-else-if="options"
      :id="id"
      :model-value="modelValue"
      :options="options"
      :placeholder="placeholder ?? 'Select one'"
      :aria-invalid="Boolean(error)"
      :aria-labelledby="`${id}-label`"
      :aria-describedby="describedBy"
      :required="required"
      :disabled="disabled"
      @update:model-value="(value) => $emit('update:modelValue', String(value ?? ''))"
    />
    <input
      v-else
      :id="id"
      :value="modelValue"
      :type="type"
      :autocomplete="autocomplete"
      :placeholder="placeholder"
      :aria-invalid="Boolean(error)"
      :aria-labelledby="`${id}-label`"
      :aria-describedby="describedBy"
      :required="required"
      :disabled="disabled"
      :readonly="readonly"
      @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    />
    <span v-if="hint" :id="`${id}-hint`" class="registration-field__hint">{{ hint }}</span>
    <span
      v-if="maxWords"
      :id="`${id}-count`"
      class="registration-field__count"
      :class="{ 'registration-field__count--over': wordCount > maxWords }"
    >
      {{ wordCount }} / {{ maxWords }} words
    </span>
    <span v-if="error" :id="`${id}-error`" class="registration-field__error">{{ error }}</span>
  </label>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import AppSelect from '@/components/AppSelect.vue'
import { countWords } from '@/registration/registration'

const props = withDefaults(
  defineProps<{
    id: string
    modelValue: string
    label: string
    type?: string
    autocomplete?: string
    placeholder?: string
    hint?: string
    error?: string
    required?: boolean
    optional?: boolean
    multiline?: boolean
    rows?: number
    wide?: boolean
    disabled?: boolean
    readonly?: boolean
    options?: { value: string; label: string }[]
    /** A word limit, counted as it's typed. */
    maxWords?: number
  }>(),
  {
    type: 'text',
    autocomplete: undefined,
    placeholder: undefined,
    hint: undefined,
    error: undefined,
    required: false,
    optional: false,
    multiline: false,
    rows: 4,
    wide: false,
    disabled: false,
    readonly: false,
    options: undefined,
    maxWords: undefined,
  },
)

defineEmits<{ 'update:modelValue': [value: string] }>()

const describedBy = computed(
  () =>
    [
      props.hint ? `${props.id}-hint` : '',
      props.maxWords ? `${props.id}-count` : '',
      props.error ? `${props.id}-error` : '',
    ]
      .filter(Boolean)
      .join(' ') || undefined,
)

const wordCount = computed(() => countWords(props.modelValue))
</script>

<style scoped>
.registration-field {
  min-width: 0;
  display: grid;
  align-content: start;
  gap: 7px;
}

.registration-field--wide {
  grid-column: 1 / -1;
}

.registration-field__label {
  display: flex;
  align-items: baseline;
  gap: 4px;
  color: var(--registration-ink);
  font-size: 0.9rem;
  font-weight: 600;
}

.registration-field__label small {
  color: var(--registration-muted);
  font-size: 0.78rem;
  font-weight: 500;
}

/* As big as the platform's other form boxes (e.g. the student sheet's). */
input,
.app-select,
textarea {
  width: 100%;
  min-height: 2.5rem;
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--registration-field-line);
  border-radius: 4px;
  outline: none;
  background: var(--white);
  color: var(--registration-ink);
  font: inherit;
  transition:
    border-color 160ms ease,
    box-shadow 160ms ease,
    background 160ms ease;
}

textarea {
  min-height: 112px;
  padding-block: 13px;
  resize: vertical;
  line-height: 1.5;
}

input::placeholder,
textarea::placeholder {
  color: var(--registration-muted);
}

input:hover,
.app-select:hover,
textarea:hover {
  border-color: #8da69d;
}

input:focus-visible,
.app-select:focus-within,
textarea:focus-visible {
  border-color: var(--registration-green);
  background: var(--white);
  box-shadow: 0 0 0 3px rgba(8, 116, 90, 0.14);
}

/* Its border and soft ring only, as the boxes beside it: no outline. */
.registration-field .app-select:has(.app-select__input:focus-visible) {
  outline: none;
}

input[aria-invalid='true'],
.app-select:has([aria-invalid='true']),
textarea[aria-invalid='true'] {
  border-color: #a93732;
}

input:disabled {
  color: #63746e;
  background: #eff3f0;
}

input:read-only:not(:disabled) {
  color: var(--registration-ink);
  background: #f4f7f3;
  cursor: default;
}

.registration-field__hint {
  color: var(--registration-muted);
  font-size: 0.8rem;
  line-height: 1.4;
}

/* Under the box, red once past the limit. */
.registration-field__count {
  color: var(--registration-muted);
  font-size: 0.8rem;
}

.registration-field__count--over {
  color: #982c27;
  font-weight: 600;
}

.registration-field__error {
  color: #982c27;
  font-size: 0.82rem;
  line-height: 1.35;
}

@media (max-width: 620px) {
  .registration-field--wide {
    grid-column: auto;
  }
}

@media (prefers-reduced-motion: reduce) {
  input,
  textarea {
    transition: none;
  }
}
</style>
