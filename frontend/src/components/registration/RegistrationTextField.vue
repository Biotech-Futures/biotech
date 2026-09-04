<template>
  <label class="registration-field" :class="{ 'registration-field--wide': wide }">
    <span class="registration-field__label">
      {{ label }}
      <small v-if="optional">Optional</small>
      <span v-else-if="required" aria-hidden="true">*</span>
    </span>
    <textarea
      v-if="multiline"
      :id="id"
      :value="modelValue"
      :rows="rows"
      :placeholder="placeholder"
      :aria-invalid="Boolean(error)"
      :aria-describedby="describedBy"
      :required="required"
      @input="$emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
    ></textarea>
    <input
      v-else
      :id="id"
      :value="modelValue"
      :type="type"
      :autocomplete="autocomplete"
      :placeholder="placeholder"
      :aria-invalid="Boolean(error)"
      :aria-describedby="describedBy"
      :required="required"
      :disabled="disabled"
      :readonly="readonly"
      @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    />
    <span v-if="hint" :id="`${id}-hint`" class="registration-field__hint">{{ hint }}</span>
    <span v-if="error" :id="`${id}-error`" class="registration-field__error">{{ error }}</span>
  </label>
</template>

<script setup lang="ts">
import { computed } from 'vue'

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
  },
)

defineEmits<{ 'update:modelValue': [value: string] }>()

const describedBy = computed(() =>
  [props.hint ? `${props.id}-hint` : '', props.error ? `${props.id}-error` : '']
    .filter(Boolean)
    .join(' ') || undefined,
)
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
  justify-content: space-between;
  gap: 12px;
  color: var(--registration-ink);
  font-size: 0.9rem;
  font-weight: 750;
}

.registration-field__label small {
  color: var(--registration-muted);
  font-size: 0.78rem;
  font-weight: 500;
}

input,
textarea {
  width: 100%;
  min-height: 50px;
  padding: 0 15px;
  border: 1px solid var(--registration-field-line);
  border-radius: 12px;
  outline: none;
  background: #fffefa;
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
  color: #73837e;
}

input:hover,
textarea:hover {
  border-color: #8da69d;
}

input:focus-visible,
textarea:focus-visible {
  border-color: var(--registration-green);
  background: #fff;
  box-shadow: 0 0 0 3px rgba(8, 116, 90, 0.14);
}

input[aria-invalid='true'],
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
