<template>
  <section class="admin-users__filters card" aria-label="Filter and search">
    <div class="admin-users__filter">
      <label class="admin-users__filter-label" for="user-search">Search</label>
      <div class="admin-users__search">
        <i class="fas fa-magnifying-glass admin-users__search-icon" aria-hidden="true"></i>
        <input
          id="user-search"
          v-model="search"
          type="search"
          class="admin-users__search-input"
          placeholder="Name or email"
          aria-label="Search users"
        />
      </div>
    </div>

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
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AdminUserCountry, AdminUserState } from '@/utils/adminAPI'
import { roleLabel } from '@/utils/userFormat'
import { USER_ROLES, type AdminUserFilters } from '@/utils/userOptions'

type FilterField = 'role' | 'country' | 'state' | 'inGroup' | 'status'

const props = defineProps<{
  filters: AdminUserFilters
  search?: string
  isStudentMode: boolean
  isRoleFixed: boolean
  filterCountries: AdminUserCountry[]
  states: AdminUserState[]
}>()

const emit = defineEmits<{
  (e: 'update:search', value: string): void
  (e: 'patch', payload: { field: FilterField; value: string }): void
}>()

const search = computed({
  get: () => props.search ?? '',
  set: (value: string) => emit('update:search', value)
})

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
.admin-users__filters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.75rem;
  padding: 1rem;
  margin-bottom: 1rem;
}

.admin-users__filter {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.admin-users__filter select {
  height: 40px;
  padding: 0.45rem 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--white);
  color: var(--charcoal);
  width: 100%;
}

.admin-users__filter-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.admin-users__search {
  position: relative;
  width: 100%;
}

.admin-users__search-input {
  width: 100%;
  height: 40px;
  padding: 0.5rem 0.75rem 0.5rem 2rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--white);
  color: var(--charcoal);
}

.admin-users__search-icon {
  position: absolute;
  left: 0.75rem;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  font-size: 0.85rem;
  pointer-events: none;
}
</style>