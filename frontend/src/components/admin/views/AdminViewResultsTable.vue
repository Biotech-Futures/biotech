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
    <template #cell-interests="{ row }">
      <div class="admin-view-table__interests" :title="toRow(row).interests?.join(', ') || undefined">
        <template v-if="toRow(row).interests?.length">
          <span
            v-for="interest in visibleInterests(toRow(row))"
            :key="interest"
            class="admin-view-table__chip"
          >
            {{ interest }}
          </span>
          <span v-if="toRow(row).interests!.length > 3" class="admin-view-table__more">
            +{{ toRow(row).interests!.length - 3 }}
          </span>
        </template>
        <span v-else>—</span>
      </div>
    </template>
    <template #cell-lastlogin="{ row }">
      {{ formatLoginDate(toRow(row).lastLogin) || 'Never' }}
    </template>
    <template #cell-yearlevel="{ row }">
      {{ toRow(row).yearLevel ?? '—' }}
    </template>
    <template #cell-group="{ row }">
      {{ toRow(row).groupName || '—' }}
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
import {
  formatLoginDate,
  labelizeCountry,
  labelizeState,
  roleLabel,
  userName,
  visibleInterests
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

// AppDataTable's `rows` prop is intentionally the loose Record<string, unknown>[]
// so it stays reusable across tables; cast back at this boundary like toRow() above.
const tableRows = computed(() => props.rows as unknown as Record<string, unknown>[])

// The row buttons get their own columns, so Actions isn't one of these.
const tableColumns = computed<DataTableColumn[]>(() =>
  props.columns
    .filter((column) => column.key !== 'actions')
    .map((column) => ({
      key: column.key,
      label: column.label,
      sortable: Boolean(column.sortable),
      wrap: column.key === 'interests'
    }))
)
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

.admin-view-table__interests {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.3rem;
}

.admin-view-table__chip {
  padding: 0.15rem 0.5rem;
  border: 1px solid var(--border-light);
  border-radius: 999px;
  background-color: var(--light-green);
  font-size: 0.8rem;
  white-space: nowrap;
}

.admin-view-table__more {
  font-size: 0.8rem;
  color: var(--text-muted);
}
</style>
