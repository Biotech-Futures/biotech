<template>
  <AppDataTable
    :columns="tableColumns"
    :rows="tableRows"
    row-key="id"
    :loading="loading"
    :selected="selected"
    :sort="sortState"
    :page="page"
    :page-size="limit"
    :total-count="totalCount ?? 0"
    :search="search"
    search-placeholder="Name or email"
    :empty-message="emptyMessage"
    :action-columns="2"
    clickable-rows
    :joined-details="showsInterests"
    :detail-for="(row) => Boolean(toRow(row).interests?.length)"
    @update:selected="emit('update:selected', $event)"
    @update:sort="emit('update:sort', $event)"
    @update:page="emit('page-change', $event)"
    @update:page-size="emit('page-size-change', $event)"
    @update:search="emit('update:search', $event)"
    @row-click="emit('row-click', $event)"
  >
    <template v-if="$slots.filters" #filters>
      <slot name="filters" />
    </template>
    <template v-if="$slots.stats" #stats>
      <slot name="stats" />
    </template>
    <template #cell-name="{ row }">
      <button type="button" class="admin-view-table__name-btn" @click.stop="emit('view', toRow(row))">
        {{ userName(toRow(row)) }}
      </button>
    </template>
    <template #cell-email="{ row }">
      <span class="admin-view-table__muted">{{ toRow(row).email || '—' }}</span>
    </template>
    <template #cell-role="{ row }">
      <span class="admin-view-table__badge">{{ roleLabel(toRow(row).role) }}</span>
    </template>
    <template #cell-pronouns="{ row }">
      {{ toRow(row).pronouns || '—' }}
    </template>
    <template #cell-mentor_group_capacity="{ row }">
      {{ toRow(row).mentorGroupCapacity ?? '—' }}
    </template>
    <template #cell-mentor_background="{ row }">
      {{ toRow(row).mentorBackgroundLabel || '—' }}
    </template>
    <template #cell-mentor_year_of_study="{ row }">
      {{ toRow(row).mentorYearOfStudy || '—' }}
    </template>
    <template #cell-mentor_field_of_study="{ row }">
      {{ toRow(row).mentorFieldOfStudy || '—' }}
    </template>
    <template #cell-supervisor_email="{ row }">
      {{ toRow(row).supervisorEmail || '—' }}
    </template>
    <template #cell-guardian_email="{ row }">
      {{ toRow(row).guardianEmail || '—' }}
    </template>
    <template #cell-guardian_permission="{ row }">
      {{ guardianPermissionLabel(toRow(row).guardianPermission) }}
    </template>
    <template #cell-school="{ row }">
      {{ toRow(row).schoolName || toRow(row).mentorInstitution || '—' }}
    </template>
    <template #cell-matched_mentor="{ row }">
      {{ toRow(row).matchedPartner || '—' }}
    </template>
    <template #cell-status="{ row }">
      <span
        class="admin-view-table__badge"
        :class="{ 'admin-view-table__badge--muted': !toRow(row).isActive }"
      >
        {{ toRow(row).isActive ? 'Active' : 'Inactive' }}
      </span>
    </template>
    <template #cell-phone="{ row }">
      {{ toRow(row).phone || '—' }}
    </template>
    <template #cell-state="{ row }">
      {{ labelizeState(toRow(row).state) }}
    </template>
    <template #cell-country="{ row }">
      {{ labelizeCountry(toRow(row).country) }}
    </template>
    <!-- Areas of interest, when the view has them, on a line of their own
         under the row and drawn as part of it, as Extend Deadline's reasons. -->
    <template v-if="showsInterests" #row-detail="{ row }">
      <div class="admin-view-table__interests">
        <span class="admin-view-table__interests-label">Areas of Interest:</span>
        {{ toRow(row).interests!.join(', ') }}
      </div>
    </template>
    <template #cell-lastlogin="{ row }">
      {{ formatShortDate(toRow(row).lastLogin) || 'Never' }}
    </template>
    <template #cell-yearlevel="{ row }">
      {{ toRow(row).yearLevel ?? '—' }}
    </template>
    <template #cell-group="{ row }">
      {{ toRow(row).groupName || '—' }}
    </template>
    <template #cell-group_number="{ row }">
      {{ toRow(row).groupNumbers || '—' }}
    </template>
    <template #cell-group_count="{ row }">
      {{ toRow(row).groupCount ?? 0 }}
    </template>
    <template #actions="{ row, column }">
      <button
        v-if="column === 0"
        type="button"
        class="btn btn-sm btn-outline"
        @click="emit('edit', toRow(row))"
      >
        Edit
      </button>
      <button
        v-else
        type="button"
        class="btn btn-sm admin-view-table__toggle-btn"
        :class="toRow(row).isActive ? 'btn-outline' : 'btn-primary'"
        :title="toRow(row).isActive ? 'Deactivate account' : 'Activate account'"
        @click="emit('toggle-active', toRow(row))"
      >
        {{ toRow(row).isActive ? 'Deactivate' : 'Activate' }}
      </button>
    </template>
  </AppDataTable>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AppDataTable, { type DataTableColumn } from '@/components/AppDataTable.vue'
import type { AdminColumn, SortState } from '@/components/admin/AdminDataTable.vue'
import type { ViewResultRow } from '@/composables/admin/useAdminViewExecuted'
import { formatShortDate } from '@/utils/date'
import {
  labelizeCountry,
  labelizeState,
  roleLabel,
  userName
} from '@/utils/userFormat'

const props = defineProps<{
  columns: AdminColumn[]
  rows: ViewResultRow[]
  loading?: boolean
  selected?: Array<string | number>
  sortState?: SortState
  page?: number
  limit?: number
  totalCount?: number
  emptyMessage?: string
  search?: string
}>()

const emit = defineEmits<{
  (e: 'update:selected', value: Array<string | number>): void
  (e: 'update:sort', value: SortState): void
  (e: 'update:search', value: string): void
  (e: 'page-change', page: number): void
  (e: 'page-size-change', size: number): void
  (e: 'row-click', row: Record<string, unknown>): void
  (e: 'view', user: ViewResultRow): void
  (e: 'edit', user: ViewResultRow): void
  (e: 'toggle-active', user: ViewResultRow): void
}>()

/** DataTable slots hand rows out as Record<string, unknown>. */
const toRow = (row: Record<string, unknown>): ViewResultRow => row as unknown as ViewResultRow

/** A student's guardian's permission. Null (no student, so the column does
 *  not apply) reads as a dash, as it does in the CSV export. */
const guardianPermissionLabel = (permission: boolean | null | undefined): string => {
  if (permission === null || permission === undefined) return '—'
  return permission ? 'Granted' : 'Not granted'
}

// AppDataTable's `rows` prop is intentionally the loose Record<string, unknown>[]
// so it stays reusable across tables; cast back at this boundary like toRow() above.
const tableRows = computed(() => props.rows as unknown as Record<string, unknown>[])

// The row buttons get their own columns, so Actions isn't one of these.
// Interests go on a line under the row, not in a column.
const tableColumns = computed<DataTableColumn[]>(() =>
  props.columns
    .filter((column) => column.key !== 'actions' && column.key !== 'interests')
    .map((column) => ({
      key: column.key,
      label: column.label,
      sortable: Boolean(column.sortable)
    }))
)
const showsInterests = computed(() => props.columns.some((column) => column.key === 'interests'))
</script>

<style scoped>
.admin-view-table__name-btn {
  border: none;
  background: transparent;
  padding: 0;
  font: inherit;
  font-weight: 600;
  color: var(--teal);
  text-align: left;
  cursor: pointer;
  transition: color 0.15s ease;
}

.admin-view-table__name-btn:hover {
  color: var(--dark-green);
  text-decoration: underline;
}

.admin-view-table__toggle-btn {
  width: 5.5rem;
  min-width: 5.5rem;
  justify-content: center;
  text-align: center;
  white-space: nowrap;
}

.admin-view-table__muted {
  color: var(--text-muted);
}

/* Role and status as plain text; inactive greyed. */
.admin-view-table__badge {
  text-transform: capitalize;
}

.admin-view-table__badge--muted {
  color: var(--text-muted);
}

/* Under a row, as Extend Deadline's reasons. */
.admin-view-table__interests {
  font-size: 0.85rem;
}

.admin-view-table__interests-label {
  color: var(--text-muted);
}
</style>
