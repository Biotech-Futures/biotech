<template>
  <!-- A mentor's weekly availability: a day and its times, as many as they
       like (stored as the admin pages' mentor availability, Monday first). -->
  <fieldset class="availability-field" :aria-describedby="error ? `${id}-error` : undefined">
    <legend>Weekly availability <small>(Optional)</small></legend>
    <p>When could you meet a group each week?</p>

    <div v-for="(slot, index) in slots" :key="index" class="availability-field__slot">
      <label class="availability-field__part">
        <span>Day</span>
        <select
          :id="`${id}-${index}-weekday`"
          v-model="slot.weekday"
          :aria-invalid="Boolean(slotError(index))"
        >
          <option value="">Select a day</option>
          <option v-for="(day, value) in WEEKDAY_NAMES" :key="day" :value="String(value)">
            {{ day }}
          </option>
        </select>
      </label>
      <label class="availability-field__part">
        <span>From</span>
        <input
          :id="`${id}-${index}-start`"
          v-model="slot.start"
          type="time"
          :aria-invalid="Boolean(slotError(index))"
        />
      </label>
      <label class="availability-field__part">
        <span>To</span>
        <input
          :id="`${id}-${index}-end`"
          v-model="slot.end"
          type="time"
          :aria-invalid="Boolean(slotError(index))"
        />
      </label>
      <button
        v-if="slots.length > 1"
        type="button"
        class="btn btn-outline-danger btn-sm availability-field__remove"
        :aria-label="`Remove time ${index + 1}`"
        @click="slots.splice(index, 1)"
      >
        <i class="fas fa-trash-can" aria-hidden="true"></i> Remove
      </button>
      <span v-if="slotError(index)" class="availability-field__error">{{ slotError(index) }}</span>
    </div>

    <button
      type="button"
      class="btn btn-outline btn-sm availability-field__add"
      @click="slots.push(createAvailabilitySlot())"
    >
      <i class="fas fa-plus" aria-hidden="true"></i> Add time
    </button>
    <span v-if="error" :id="`${id}-error`" class="availability-field__error">{{ error }}</span>
  </fieldset>
</template>

<script setup lang="ts">
import {
  createAvailabilitySlot,
  WEEKDAY_NAMES,
  type AvailabilitySlot,
} from '@/registration/registration'

const props = withDefaults(
  defineProps<{
    id: string
    /** Where its errors are: ``${prefix}.${index}`` for a slot's. */
    prefix: string
    errors: Record<string, string>
    error?: string
  }>(),
  { error: undefined },
)

const slots = defineModel<AvailabilitySlot[]>({ required: true })

const slotError = (index: number) => props.errors[`${props.prefix}.${index}`]
</script>

<style scoped>
.availability-field {
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 0;
  display: grid;
  gap: 14px;
}

legend {
  padding: 0;
  color: var(--registration-ink);
  font-size: 0.92rem;
  font-weight: 600;
}

legend small {
  color: var(--registration-muted);
  font-size: 0.78rem;
  font-weight: 500;
}

p {
  margin: 5px 0 0;
  color: var(--registration-muted);
  font-size: 0.86rem;
}

/* A day and its times in a row, Remove at its end. */
.availability-field__slot {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr) minmax(0, 1fr) auto;
  align-items: end;
  gap: 12px;
}

.availability-field__part {
  display: grid;
  gap: 6px;
  color: var(--registration-ink);
  font-size: 0.85rem;
  font-weight: 600;
}

/* As big as the form's other boxes. */
select,
input {
  width: 100%;
  min-height: 2.5rem;
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--registration-field-line);
  border-radius: 4px;
  background: var(--white);
  color: var(--registration-ink);
  font: inherit;
  font-weight: 400;
}

select:focus-visible,
input:focus-visible {
  outline: none;
  border-color: var(--registration-green);
  box-shadow: 0 0 0 3px rgba(8, 116, 90, 0.14);
}

[aria-invalid='true'] {
  border-color: #a93732;
}

.availability-field__remove {
  min-height: 2.5rem;
}

.availability-field__add {
  justify-self: start;
}

.availability-field__error {
  grid-column: 1 / -1;
  color: #982c27;
  font-size: 0.82rem;
}

@media (max-width: 620px) {
  .availability-field__slot {
    grid-template-columns: 1fr 1fr;
  }

  .availability-field__part:first-child {
    grid-column: 1 / -1;
  }
}
</style>
