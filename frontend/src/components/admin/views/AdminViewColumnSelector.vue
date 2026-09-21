<template>
  <div class="column-selector">
    <div class="column-selector__header">
      <span class="column-selector__label">Select columns to display in this view:</span>
      <span class="column-selector__badge">{{ modelValue.length }} selected</span>
    </div>

    <fieldset class="column-selector__grid">
      <legend class="sr-only">Visible columns</legend>
      <label
        v-for="col in AVAILABLE_COLUMNS"
        :key="col.key"
        class="column-selector__checkbox-label"
      >
        <input
          type="checkbox"
          :checked="isSelected(col.key)"
          class="column-selector__checkbox"
          @change="toggleColumn(col.key)"
        />
        <span class="column-selector__name">{{ col.label }}</span>
      </label>
    </fieldset>
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
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 0.5rem;
  border: none;
  padding: 0;
  margin: 0.25rem 0 0;
}

.column-selector__checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: var(--charcoal);
  cursor: pointer;
  user-select: none;
}

.column-selector__checkbox {
  accent-color: var(--dark-green);
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.column-selector__name {
  font-size: 0.875rem;
  color: var(--charcoal);
}
</style>
