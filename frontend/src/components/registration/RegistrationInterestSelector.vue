<template>
  <fieldset class="interest-selector" :aria-describedby="error ? `${id}-error` : undefined">
    <legend>{{ label }} <span aria-hidden="true">*</span></legend>
    <p v-if="description">{{ description }}</p>
    <div class="interest-selector__options">
      <label v-for="interest in INTEREST_CATEGORIES" :key="interest">
        <input
          v-model="selection"
          type="checkbox"
          :name="id"
          :value="interest"
          :aria-invalid="Boolean(error)"
        />
        <span>{{ interest }}</span>
      </label>
    </div>
    <span v-if="error" :id="`${id}-error`" class="interest-selector__error">{{ error }}</span>
  </fieldset>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import { INTEREST_CATEGORIES } from '@/registration/registration'

const props = withDefaults(
  defineProps<{
    id: string
    modelValue: string[]
    label?: string
    description?: string
    error?: string
  }>(),
  {
    label: 'Relevant interests',
    description: undefined,
    error: undefined,
  },
)

const emit = defineEmits<{ 'update:modelValue': [value: string[]] }>()

const selection = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})
</script>

<style scoped>
.interest-selector {
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 0;
}

legend {
  padding: 0;
  color: var(--registration-ink);
  font-size: 0.92rem;
  font-weight: 750;
}

p {
  margin: 5px 0 14px;
  color: var(--registration-muted);
  font-size: 0.86rem;
  line-height: 1.45;
}

.interest-selector__options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  border-top: 1px solid var(--registration-line);
}

label {
  min-height: 48px;
  padding: 10px 12px 10px 2px;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  border-bottom: 1px solid var(--registration-line);
  color: var(--registration-ink);
  font-size: 0.85rem;
  line-height: 1.35;
  cursor: pointer;
}

label:nth-child(odd) {
  margin-right: 16px;
}

input {
  flex: 0 0 auto;
  width: 17px;
  height: 17px;
  margin-top: 1px;
  accent-color: var(--registration-green);
}

input:focus-visible {
  outline: 3px solid rgba(8, 116, 90, 0.2);
  outline-offset: 3px;
}

.interest-selector__error {
  display: block;
  margin-top: 8px;
  color: #982c27;
  font-size: 0.82rem;
}

@media (max-width: 680px) {
  .interest-selector__options {
    grid-template-columns: 1fr;
  }

  label:nth-child(odd) {
    margin-right: 0;
  }
}
</style>
