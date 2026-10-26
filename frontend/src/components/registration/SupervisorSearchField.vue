<template>
  <!-- An existing supervisor, found by their email and picked from the list
       (their name and school beside it): laid out as the form's other fields. -->
  <label class="supervisor-search registration-field--wide">
    <span :id="`${id}-label`" class="supervisor-search__label">
      {{ label }}
      <span class="required-mark" aria-hidden="true">*</span>
    </span>
    <span class="supervisor-search__box">
      <i class="fas fa-magnifying-glass supervisor-search__icon" aria-hidden="true"></i>
      <input
        :id="id"
        class="app-input app-input--wide"
        :value="modelValue"
        type="text"
        required
        autocomplete="off"
        placeholder="Search by email"
        :aria-invalid="Boolean(error)"
        :aria-labelledby="`${id}-label`"
        :aria-describedby="error ? `${id}-error` : undefined"
        @input="onInput"
        @focus="isOpen = true"
        @blur="isOpen = false"
      />
      <ul v-if="isOpen && suggestions.length" class="supervisor-search__list" role="listbox">
        <li v-for="supervisor in suggestions" :key="supervisor.user_id">
          <button
            type="button"
            class="supervisor-search__option"
            @mousedown.prevent="pick(supervisor)"
          >
            <span class="supervisor-search__email">{{ supervisor.email }}</span>
            <span class="supervisor-search__who">
              {{ [supervisor.name, supervisor.school].filter(Boolean).join(' · ') }}
            </span>
          </button>
        </li>
      </ul>
    </span>
    <span v-if="error" :id="`${id}-error`" class="supervisor-search__error">{{ error }}</span>
  </label>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

import type { RegistrationSupervisor } from '@/utils/managementAPI'

const props = defineProps<{
  id: string
  modelValue: string
  label: string
  /** Every supervisor to choose from. */
  supervisors: RegistrationSupervisor[]
  error?: string
}>()

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const isOpen = ref(false)

// Up to 8 whose email has what's typed.
const suggestions = computed(() => {
  const typed = props.modelValue.trim().toLowerCase()
  if (!typed) return []
  return props.supervisors.filter((supervisor) => supervisor.email.toLowerCase().includes(typed)).slice(0, 8)
})

const onInput = (event: Event) => {
  isOpen.value = true
  emit('update:modelValue', (event.target as HTMLInputElement).value)
}

const pick = (supervisor: RegistrationSupervisor) => {
  isOpen.value = false
  emit('update:modelValue', supervisor.email)
}
</script>

<style scoped>
/* As RegistrationTextField's label, box and error. */
.supervisor-search {
  min-width: 0;
  display: grid;
  align-content: start;
  gap: 7px;
}

.supervisor-search__label {
  display: flex;
  align-items: baseline;
  gap: 4px;
  color: var(--registration-ink);
  font-size: 0.9rem;
  font-weight: 600;
}

.supervisor-search__box {
  position: relative;
  display: block;
}

.supervisor-search__icon {
  position: absolute;
  left: 0.7rem;
  top: 50%;
  transform: translateY(-50%);
  color: var(--registration-muted);
  font-size: 0.85rem;
  pointer-events: none;
}

/* The shared box (app-input), with room on the left for the magnifier, in
   registration's colours. */
input {
  padding-left: 2.1rem;
  border-color: var(--registration-field-line);
  outline: none;
  background: var(--white);
  color: var(--registration-ink);
  font: inherit;
  transition:
    border-color 160ms ease,
    box-shadow 160ms ease;
}

input::placeholder {
  color: var(--registration-muted);
}

input:hover {
  border-color: #8da69d;
}

input:focus-visible {
  border-color: var(--registration-green);
  box-shadow: 0 0 0 3px rgba(8, 116, 90, 0.14);
}

input[aria-invalid='true'] {
  border-color: #a93732;
}

/* The matches, under the box, as Extend Deadline's group search has them. */
.supervisor-search__list {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  z-index: 30;
  max-height: 16rem;
  margin: 0;
  padding: 0.25rem;
  overflow-y: auto;
  list-style: none;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--surface-elevated);
  box-shadow: 0 6px 18px var(--shadow);
}

.supervisor-search__option {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 0.75rem;
  width: 100%;
  padding: 0.4rem 0.5rem;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--registration-ink);
  font: inherit;
  font-size: 0.88rem;
  text-align: left;
  cursor: pointer;
}

.supervisor-search__option:hover {
  background: var(--light-green);
}

.supervisor-search__who {
  color: var(--registration-muted);
  font-size: 0.8rem;
}

.supervisor-search__error {
  color: #a93732;
  font-size: 0.82rem;
}
</style>
