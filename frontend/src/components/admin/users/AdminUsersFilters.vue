<template>
  <div class="admin-users__filters" role="group" aria-label="Filters">

    <!-- The white dropdowns the user panel has: Country's to search, as
         its list is long; the others just to pick from. -->
    <div v-if="!isRoleFixed" class="admin-users__filter">
      <label class="admin-users__filter-label" for="role-filter">Role</label>
      <AppSelect
        class="table-filter"
        id="role-filter"
        :model-value="filters.role"
        :options="roleOptions"
        :searchable="false"
        @update:model-value="(value) => emitPatch('role', value)"
      />
    </div>

    <div class="admin-users__filter">
      <label class="admin-users__filter-label" for="country-filter">Country</label>
      <AppSelect
        class="table-filter"
        id="country-filter"
        :model-value="filters.country"
        :options="countryOptions"
        placeholder="Search countries"
        empty-text="No country matches"
        @update:model-value="(value) => emitPatch('country', value)"
      />
    </div>

    <div class="admin-users__filter">
      <label class="admin-users__filter-label" for="state-filter">State</label>
      <AppSelect
        class="table-filter"
        id="state-filter"
        :model-value="filters.state"
        :options="stateOptions"
        :searchable="false"
        @update:model-value="(value) => emitPatch('state', value)"
      />
    </div>

    <div v-if="isStudentMode" class="admin-users__filter">
      <label class="admin-users__filter-label" for="in-group-filter">In group</label>
      <AppSelect
        class="table-filter"
        id="in-group-filter"
        :model-value="filters.inGroup"
        :options="IN_GROUP_OPTIONS"
        :searchable="false"
        @update:model-value="(value) => emitPatch('inGroup', value)"
      />
    </div>

    <div class="admin-users__filter">
      <label class="admin-users__filter-label" for="status-filter">Status</label>
      <AppSelect
        class="table-filter"
        id="status-filter"
        :model-value="filters.status"
        :options="STATUS_OPTIONS"
        :searchable="false"
        @update:model-value="(value) => emitPatch('status', value)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppSelect, { type AppSelectOption, type AppSelectValue } from '@/components/AppSelect.vue'
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

const roleOptions = computed<AppSelectOption[]>(() => [
  { value: 'all', label: 'All roles' },
  ...USER_ROLES.map((role) => ({ value: role, label: roleLabel(role) }))
])

const countryOptions = computed<AppSelectOption[]>(() => [
  { value: 'all', label: 'All countries' },
  ...filterCountryNames.value.map((name) => ({ value: name, label: name }))
])

const stateOptions = computed<AppSelectOption[]>(() => [
  { value: 'all', label: 'All states' },
  ...visibleStates.value.map((state) => ({ value: state.stateName, label: stateOptionLabel(state) }))
])

const IN_GROUP_OPTIONS: AppSelectOption[] = [
  { value: 'all', label: 'All students' },
  { value: 'yes', label: 'In a group' },
  { value: 'no', label: 'Not in a group' }
]

const STATUS_OPTIONS: AppSelectOption[] = [
  { value: 'all', label: 'All statuses' },
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' }
]

const emitPatch = (field: FilterField, value: AppSelectValue) => {
  emit('patch', { field, value: String(value) })
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

.admin-users__filter-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
</style>
