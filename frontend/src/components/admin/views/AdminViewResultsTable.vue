<template>
  <AdminDataTable
    :columns="columns"
    :rows="tableRows"
    row-key="id"
    :loading="loading"
    :sort-state="sortState"
    :show-pagination="true"
    :page="page"
    :page-size="limit"
    :total-count="totalCount"
    :page-size-options="pageSizeOptions"
    :empty-message="emptyMessage"
    pager-label="View results pagination"
    @update:sort="emit('update:sort', $event)"
    @page-change="emit('page-change', $event)"
    @page-size-change="emit('page-size-change', $event)"
  >
    <template #cell-name="{ row }">
      {{ userName(toRow(row)) }}
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
  </AdminDataTable>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AdminDataTable, { type AdminColumn, type SortState } from '@/components/admin/AdminDataTable.vue'
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
  sortState?: SortState
  page?: number
  limit?: number
  totalCount?: number
  emptyMessage?: string
  pageSizeOptions?: number[]
}>()

const emit = defineEmits<{
  (e: 'update:sort', value: SortState): void
  (e: 'page-change', page: number): void
  (e: 'page-size-change', size: number): void
}>()

/** DataTable slots hand rows out as Record<string, unknown>. */
const toRow = (row: Record<string, unknown>): ViewResultRow => row as unknown as ViewResultRow

// AdminDataTable's `rows` prop is intentionally the loose Record<string, unknown>[]
// so it stays reusable across tables; cast back at this boundary like toRow() above.
const tableRows = computed(() => props.rows as unknown as Record<string, unknown>[])
</script>

<style scoped>
.admin-view-table__muted {
  color: var(--text-muted);
}

.admin-view-table__badge {
  display: inline-block;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  background-color: var(--light-green);
  color: var(--dark-green);
  text-transform: capitalize;
}

.admin-view-table__badge--muted {
  background-color: var(--bg-light);
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
