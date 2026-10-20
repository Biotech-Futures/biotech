<template>
  <fieldset class="interest-selector" :aria-describedby="error ? `${id}-error` : undefined">
    <legend>{{ label }} <span v-if="showRequired" class="required-mark" aria-hidden="true">*</span></legend>
    <p v-if="description">{{ description }}</p>
    <div class="interest-selector__options">
      <label v-for="interest in options ?? INTEREST_CATEGORIES" :key="interest">
        <input
          v-model="selection"
          type="checkbox"
          :name="id"
          :value="interest"
          :aria-invalid="Boolean(error)"
        />
        <span>
          {{ interest }}
          <small v-if="counts" class="interest-selector__count">
            {{ counts[interest] ?? 0 }} of {{ total }}
          </small>
        </span>
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
    /** Whether its label has the * of a required field. */
    showRequired?: boolean
    /** The areas in this order (all of them), else as listed. */
    options?: readonly string[]
    /** How many chose each area, shown "2 of 3" with ``total``. */
    counts?: Record<string, number>
    total?: number
  }>(),
  {
    label: 'Relevant interests',
    description: undefined,
    error: undefined,
    showRequired: true,
    options: undefined,
    counts: undefined,
    total: 0,
  },
)

const emit = defineEmits<{ 'update:modelValue': [value: string[]] }>()

const selection = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})
</script>

<style scoped>
/* In a box, its heading on the line, as the dashboard shows them. */
.interest-selector {
  min-width: 0;
  margin: 0;
  padding: 10px 16px 22px;
  border: 1px solid var(--registration-field-line);
  border-radius: 6px;
}

legend {
  padding: 0 6px;
  color: var(--registration-ink);
  font-size: 0.92rem;
  font-weight: 600;
}

/* Close under the heading, with room below it before the options. */
p {
  margin: -4px 0 0;
  color: var(--registration-muted);
  font-size: 0.86rem;
  line-height: 1.45;
}

/* The options in two columns, with no lines between them: as far below
   the heading (with the box's padding) as they are from each other. */
.interest-selector__options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 30px 16px;
  margin-top: 20px;
}

p + .interest-selector__options {
  margin-top: 30px;
}

label {
  padding: 0 12px 0 2px;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  color: var(--registration-ink);
  font-size: 0.85rem;
  line-height: 1.35;
  cursor: pointer;
}

/* In rem, as its text is, so it stays centred on the first line at any
   text size: half the line (0.85rem at 1.35) less half the box. */
input {
  flex: 0 0 auto;
  width: 1.0625rem;
  height: 1.0625rem;
  margin-top: calc((0.85rem * 1.35 - 1.0625rem) / 2);
  accent-color: var(--registration-green);
}

.interest-selector__count {
  margin-left: 4px;
  color: var(--registration-muted);
  font-size: 0.78rem;
  white-space: nowrap;
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
}
</style>
