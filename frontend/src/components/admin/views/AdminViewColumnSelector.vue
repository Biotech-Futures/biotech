<template>
  <div class="column-selector">
    <div class="column-selector__header">
      <span class="column-selector__label">Select columns to display in this view:</span>
      <span class="column-selector__badge">{{ modelValue.length }} selected</span>
    </div>

    <div class="column-selector__grid">
      <label
        v-for="col in AVAILABLE_COLUMNS"
        :key="col.key"
        class="column-selector__item"
        :class="{ 'column-selector__item--selected': isSelected(col.key) }"
      >
        <input
          type="checkbox"
          :checked="isSelected(col.key)"
          class="column-selector__checkbox"
          @change="toggleColumn(col.key)"
        />
        <span class="column-selector__name">{{ col.label }}</span>
      </label>
    </div>
  </div>
</template>

<script setup lang="ts">
export interface ColumnOption {
  key: string
  label: string
}

const AVAILABLE_COLUMNS: ColumnOption[] = [
  { key: 'name', label: 'Full Name' },
  { key: 'email', label: 'Email' },
  { key: 'role', label: 'Role' },
  { key: 'school', label: 'School / Institution' },
  { key: 'matched_mentor', label: 'Matched Mentor / Group' },
  { key: 'status', label: 'Status' },
  { key: 'phone', label: 'Phone' },
  { key: 'state', label: 'State' },
  { key: 'interests', label: 'Interests' },
  { key: 'lastLogin', label: 'Last Login' },
]

const props = defineProps<{
  modelValue: string[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string[]): void
}>()

const isSelected = (key: string): boolean => {
  return props.modelValue.includes(key)
}

const toggleColumn = (key: string) => {
  const current = [...props.modelValue]
  const idx = current.indexOf(key)
  if (idx >= 0) {
    if (current.length > 1) {
      current.splice(idx, 1)
    }
  } else {
    current.push(key)
  }
  emit('update:modelValue', current)
}
</script>

<style scoped>
.column-selector {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.column-selector__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.column-selector__label {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--charcoal);
}

.column-selector__badge {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--dark-green);
  background-color: var(--light-green);
  padding: 0.15rem 0.5rem;
  border-radius: 9999px;
}

.column-selector__grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.5rem;
}

.column-selector__item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.45rem 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background-color: var(--surface-elevated, #ffffff);
  cursor: pointer;
  transition: all 0.15s ease-in-out;
  user-select: none;
}

.column-selector__item:hover {
  background-color: var(--bg-light);
  border-color: var(--dark-green);
}

.column-selector__item--selected {
  border-color: var(--dark-green);
  background-color: rgba(1, 113, 81, 0.05);
}

.column-selector__checkbox {
  accent-color: var(--dark-green);
  cursor: pointer;
}

.column-selector__name {
  font-size: 0.85rem;
  color: var(--charcoal);
}

@media (max-width: 600px) {
  .column-selector__grid {
    grid-template-columns: 1fr;
  }
}
</style>
