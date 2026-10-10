<template>
  <div class="admin-users__filters" role="group" aria-label="Filters">

    <div v-if="!isRoleFixed" class="admin-users__filter">
      <label class="admin-users__filter-label" for="role-filter">Role</label>
      <select id="role-filter" :value="filters.role" @change="emitPatch('role', $event)">
        <option value="all">All roles</option>
        <option v-for="role in USER_ROLES" :key="role" :value="role">{{ roleLabel(role) }}</option>
      </select>
    </div>

    <div class="admin-users__filter">
      <label class="admin-users__filter-label" for="country-filter">Country</label>
      <select id="country-filter" :value="filters.country" @change="emitPatch('country', $event)">
        <option value="all">All countries</option>
        <option v-for="name in filterCountryNames" :key="name" :value="name">{{ name }}</option>
      </select>
    </div>

    <div class="admin-users__filter">
      <label class="admin-users__filter-label" for="state-filter">State</label>
      <select id="state-filter" :value="filters.state" @change="emitPatch('state', $event)">
        <option value="all">All states</option>
        <option v-for="state in visibleStates" :key="state.id" :value="state.stateName">
          {{ stateOptionLabel(state) }}
        </option>
      </select>
    </div>

    <div v-if="isStudentMode" class="admin-users__filter">
      <label class="admin-users__filter-label" for="in-group-filter">In group</label>
      <select id="in-group-filter" :value="filters.inGroup" @change="emitPatch('inGroup', $event)">
        <option value="all">All students</option>
        <option value="yes">In a group</option>
        <option value="no">Not in a group</option>
      </select>
    </div>

    <div class="admin-users__filter">
      <label class="admin-users__filter-label" for="status-filter">Status</label>
      <select id="status-filter" :value="filters.status" @change="emitPatch('status', $event)">
        <option value="all">All statuses</option>
        <option value="active">Active</option>
        <option value="inactive">Inactive</option>
      </select>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AdminUserCountry, AdminUserState } from '@/utils/adminAPI'
import { roleLabel } from '@/utils/userFormat'
import { USER_ROLES, type AdminUserFilters } from '@/utils/userOptions'

type FilterField = 'role' | 'country' | 'state' | 'inGroup' | 'status'

const props = defineProps<{
  filters: AdminUserFilters
  isStudentMode: boolean
  isRoleFixed: boolean
  filterCountries: AdminUserCountry[]
  states: AdminUserState[]
}>()

const emit = defineEmits<{
  (e: 'patch', payload: { field: FilterField; value: string }): void
}>()

const filterCountryNames = computed(() =>
  [...new Set(props.filterCountries.map((country) => country.countryName))].sort((a, b) =>
    a.localeCompare(b)
  )
)

const visibleStates = computed(() => {
  if (props.filters.country === 'all') return props.states
  return props.states.filter((state) => state.countryName === props.filters.country)
})

const stateOptionLabel = (state: AdminUserState) =>
  props.filters.country === 'all' && state.countryName
    ? `${state.stateName} · ${state.countryName}`
    : state.stateName

const emitPatch = (field: FilterField, event: Event) => {
  emit('patch', { field, value: (event.target as HTMLSelectElement).value })
}
</script>

<style scoped>
/* Laid out beside Search in the table's search card, and drawn like it. */
.admin-users__filters {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 0.75rem 1rem;
}

.admin-users__filter {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.admin-users__filter select {
  min-width: 9rem;
  padding: 0.45rem 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  font-size: 0.9rem;
  font-family: inherit;
  background-color: var(--surface-elevated);
  color: var(--teal);
}

.admin-users__filter select:focus {
  outline: none;
  border-color: var(--dark-green);
}

.admin-users__filter-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
</style>
