<template>
  <div class="system-logs__filters" role="group" aria-label="Filters">
    <div class="system-logs__filter">
      <label class="system-logs__filter-label" for="log-from-filter">From</label>
      <input
        id="log-from-filter"
        type="date"
        :value="filters.fromDate"
        :max="filters.toDate || undefined"
        @change="emitPatch('fromDate', $event)"
      />
    </div>

    <div class="system-logs__filter">
      <label class="system-logs__filter-label" for="log-to-filter">To</label>
      <input
        id="log-to-filter"
        type="date"
        :value="filters.toDate"
        :min="filters.fromDate || undefined"
        @change="emitPatch('toDate', $event)"
      />
    </div>

    <div class="system-logs__filter">
      <label class="system-logs__filter-label" for="log-level-filter">Level</label>
      <select id="log-level-filter" :value="filters.level" @change="emitPatch('level', $event)">
        <option v-for="option in LEVEL_OPTIONS" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>
    </div>

    <!-- Text filters apply on Enter or on leaving the field, not per keystroke. -->
    <div class="system-logs__filter">
      <label class="system-logs__filter-label" for="log-source-filter">Source</label>
      <input
        id="log-source-filter"
        type="text"
        placeholder="e.g. apps.services"
        :value="filters.source"
        @change="emitPatch('source', $event)"
      />
    </div>

    <div class="system-logs__filter">
      <label class="system-logs__filter-label" for="log-user-filter">User</label>
      <input
        id="log-user-filter"
        type="text"
        placeholder="ID or email"
        :value="filters.user"
        @change="emitPatch('user', $event)"
      />
    </div>

    <div class="system-logs__filter">
      <label class="system-logs__filter-label" for="log-request-filter">Request ID</label>
      <input
        id="log-request-filter"
        type="text"
        :value="filters.requestId"
        @change="emitPatch('requestId', $event)"
      />
    </div>

    <button
      v-if="hasActiveFilters"
      type="button"
      class="btn btn-sm btn-outline system-logs__clear"
      @click="emit('clear')"
    >
      Clear filters
    </button>
  </div>
</template>

<script setup lang="ts">
import type { SystemLogFilterField, SystemLogFilters } from '@/composables/admin/useAdminSystemLogs'

// The lowest level shown; the backend keeps WARNING and above, and INFO only
// from the sign-in and email loggers.
const LEVEL_OPTIONS = [
  { value: '', label: 'All levels' },
  { value: 'INFO', label: 'Info and above' },
  { value: 'WARNING', label: 'Warning and above' },
  { value: 'ERROR', label: 'Error and above' },
  { value: 'CRITICAL', label: 'Critical only' }
]

defineProps<{
  filters: SystemLogFilters
  hasActiveFilters: boolean
}>()

const emit = defineEmits<{
  (e: 'patch', payload: { field: SystemLogFilterField; value: string }): void
  (e: 'clear'): void
}>()

const emitPatch = (field: SystemLogFilterField, event: Event) => {
  emit('patch', { field, value: (event.target as HTMLInputElement | HTMLSelectElement).value })
}
</script>

<style scoped>
/* Beside Search in the table's search card, drawn like the users filters. */
.system-logs__filters {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 0.75rem 1rem;
}

.system-logs__filter {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.system-logs__filter select,
.system-logs__filter input {
  min-width: 9rem;
  padding: 0.45rem 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  font-size: 0.9rem;
  font-family: inherit;
  background-color: var(--surface-elevated);
  color: var(--teal);
}

.system-logs__filter select:focus,
.system-logs__filter input:focus {
  outline: none;
  border-color: var(--dark-green);
}

.system-logs__filter-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.system-logs__clear {
  align-self: flex-end;
}
</style>
