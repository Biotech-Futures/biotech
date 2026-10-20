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
      class="app-input app-input--wide"
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
      class="app-input"
      :class="{ 'app-input--wide': wide }"
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
    <!-- With suggestions, they drop down under it as the site's lists do. -->
    <span v-else class="registration-field__control">
      <input
        :id="id"
        class="app-input"
        :class="{ 'app-input--wide': wide }"
        :value="modelValue"
        :type="digits ? 'number' : type"
        :autocomplete="suggestions?.length ? 'off' : autocomplete"
        :role="suggestions?.length ? 'combobox' : undefined"
        :aria-autocomplete="suggestions?.length ? 'list' : undefined"
        :aria-expanded="suggestions?.length ? listShown : undefined"
        :aria-controls="suggestions?.length ? `${id}-suggestions` : undefined"
        :aria-activedescendant="listShown && active >= 0 ? `${id}-suggestion-${active}` : undefined"
        :placeholder="placeholder"
        :aria-invalid="Boolean(error)"
        :aria-labelledby="`${id}-label`"
        :aria-describedby="describedBy"
        :required="required"
        :disabled="disabled"
        :readonly="readonly"
        :inputmode="digits ? 'numeric' : undefined"
        :maxlength="digits ? undefined : maxLength"
        :min="min"
        :max="max"
        :step="digits ? 1 : undefined"
        @input="onInput"
        @focus="openList"
        @blur="listOpen = false"
        @keydown="onKeydown"
        @paste="digits && refuseNonDigitPaste($event)"
      />
      <!-- Offered as it's typed (other members' schools); anything else can be typed. -->
      <ul v-if="listShown" :id="`${id}-suggestions`" class="registration-field__suggestions" role="listbox">
        <li
          v-for="(suggestion, index) in shownSuggestions"
          :id="`${id}-suggestion-${index}`"
          :key="suggestion"
          role="option"
          class="registration-field__suggestion"
          :class="{ 'is-active': index === active }"
          :aria-selected="index === active"
          @mousedown.prevent="pick(suggestion)"
          @mouseenter="active = index"
        >
          {{ suggestion }}
        </li>
      </ul>
    </span>
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
import { computed, ref } from 'vue'

import AppSelect from '@/components/AppSelect.vue'
import { countWords } from '@/registration/registration'
import { keptDigits, refuseNonDigitKey, refuseNonDigitPaste } from '@/utils/digitsOnly'

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
    /** A number box, with its arrows, taking whole numbers alone (at most
     *  `maxLength` digits, from `min` to `max` by its arrows). */
    digits?: boolean
    maxLength?: number
    min?: number
    max?: number
    /** Offered as it's typed, any other answer still allowed. */
    suggestions?: string[]
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
    digits: false,
    maxLength: undefined,
    min: undefined,
    max: undefined,
    suggestions: undefined,
  },
)

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

// Suggestions: open while it has focus, those holding what's typed (but not
// just what's typed), picked by a click or the arrows and Enter.
const listOpen = ref(false)
const active = ref(-1)
const shownSuggestions = computed(() => {
  const typed = props.modelValue.trim().toLowerCase()
  return (props.suggestions ?? []).filter(
    (suggestion) => suggestion.toLowerCase().includes(typed) && suggestion.toLowerCase() !== typed,
  )
})
const listShown = computed(() => listOpen.value && shownSuggestions.value.length > 0)

const openList = () => {
  listOpen.value = true
  active.value = -1
}

const pick = (suggestion: string) => {
  emit('update:modelValue', suggestion)
  listOpen.value = false
}

const onKeydown = (event: KeyboardEvent) => {
  if (props.digits) refuseNonDigitKey(event)
  if (!props.suggestions?.length) return
  const count = shownSuggestions.value.length
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    if (!count) return
    event.preventDefault()
    listOpen.value = true
    const step = event.key === 'ArrowDown' ? 1 : -1
    active.value = (active.value + step + count) % count
  } else if (event.key === 'Enter' && listShown.value && active.value >= 0) {
    event.preventDefault()
    pick(shownSuggestions.value[active.value])
  } else if (event.key === 'Escape' && listShown.value) {
    event.preventDefault()
    listOpen.value = false
  }
}

// What's typed; a number box's digits alone, cut to its length.
const onInput = (event: Event) => {
  listOpen.value = true
  active.value = -1
  const field = event.target as HTMLInputElement
  emit('update:modelValue', props.digits ? keptDigits(field, props.maxLength) : field.value)
}

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
/* The box, and its suggestions under it. */
.registration-field__control {
  position: relative;
  display: block;
}

/* As wide as the shared box (app-input) in it, so its list is too. */
.registration-field__control:has(> .app-input:not(.app-input--wide)) {
  max-width: 320px;
}

/* As the site's dropdown lists (AppSelect's). */
.registration-field__suggestions {
  position: absolute;
  z-index: 20;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  box-sizing: border-box;
  max-height: 16rem;
  margin: 0;
  padding: 0.25rem;
  overflow-y: auto;
  list-style: none;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--surface-elevated, var(--white));
  box-shadow: 0 6px 18px var(--shadow, rgba(0, 0, 0, 0.12));
}

.registration-field__suggestion {
  padding: 0.3rem 0.5rem;
  border-radius: 4px;
  overflow: hidden;
  color: var(--teal);
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}

.registration-field__suggestion.is-active {
  background: var(--light-green);
}

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

/* The shared box (app-input), in registration's colours. */
input,
.app-select,
textarea {
  border-color: var(--registration-field-line);
  outline: none;
  background: var(--white);
  color: var(--registration-ink);
  transition:
    border-color 160ms ease,
    box-shadow 160ms ease,
    background 160ms ease;
}

/* A long answer: room for a few lines at least. */
textarea {
  min-height: 112px;
  resize: vertical;
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
