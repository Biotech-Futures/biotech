<template>
  <AdminDataTable
    :columns="columns"
    :rows="rows"
    row-key="id"
    :loading="loading"
    selectable
    :selected="selected"
    :sort-state="sortState"
    :show-pagination="true"
    :page="page"
    :page-size="limit"
    :total-count="totalCount"
    :page-size-options="pageSizeOptions"
    :empty-message="emptyMessage"
    :pager-label="pagerLabel"
    :select-all-label="selectAllLabel"
    @update:selected="emit('update:selected', $event)"
    @update:sort="emit('update:sort', $event)"
    @page-change="emit('page-change', $event)"
    @page-size-change="emit('page-size-change', $event)"
    @row-click="emit('row-click', $event)"
  >
    <template #cell-name="{ row }">
      <button type="button" class="admin-users__name-btn" @click.stop="emit('view', toAdminUser(row))">
        {{ userName(toAdminUser(row)) }}
      </button>
    </template>
    <template #cell-email="{ row }">
      <span class="admin-users__email">{{ toAdminUser(row).email || '—' }}</span>
    </template>
    <template #cell-role="{ row }">
      <span class="admin-users__role-badge">{{ roleLabel(toAdminUser(row).role) }}</span>
    </template>
    <template #cell-student="{ row }">
      <div class="admin-users__student-cell">
        <button type="button" class="admin-users__name-btn" @click.stop="emit('view', toAdminUser(row))">
          {{ userName(toAdminUser(row)) }}
        </button>
        <span class="admin-users__email">{{ toAdminUser(row).email || '—' }}</span>
      </div>
    </template>
    <template #cell-school="{ row }">
      {{ toAdminUser(row).schoolName || '—' }}
    </template>
    <template #cell-year="{ row }">
      {{ toAdminUser(row).yearLevel ?? '—' }}
    </template>
    <template #cell-country="{ row }">
      {{ labelizeCountry(toAdminUser(row).country) }}
    </template>
    <template #cell-state="{ row }">
      {{ labelizeState(toAdminUser(row).state) }}
    </template>
    <template v-if="isStudentMode" #cell-group="{ row }">
      <span :title="toAdminUser(row).groupId ? `Group ID ${toAdminUser(row).groupId}` : undefined">
        {{ toAdminUser(row).groupName || '—' }}
      </span>
    </template>
    <template #cell-interests="{ row }">
      <div class="admin-users__interests" :title="toAdminUser(row).interests?.join(', ') || undefined">
        <template v-if="toAdminUser(row).interests?.length">
          <span
            v-for="interest in visibleInterests(toAdminUser(row))"
            :key="interest"
            class="admin-users__interest-chip"
          >
            {{ interest }}
          </span>
          <span v-if="toAdminUser(row).interests!.length > 3" class="admin-users__interest-more">
            +{{ toAdminUser(row).interests!.length - 3 }}
          </span>
        </template>
        <span v-else>—</span>
      </div>
    </template>
    <template #cell-status="{ row }">
      <span
        class="admin-users__status-badge"
        :class="{ 'admin-users__status-badge--inactive': !toAdminUser(row).isActive }"
      >
        {{ toAdminUser(row).isActive ? 'Active' : 'Inactive' }}
      </span>
    </template>
    <template #cell-loggedIn="{ row }">
      <div class="admin-users__logged-in">
        <span
          v-if="toAdminUser(row).hasLoggedIn"
          class="admin-users__logged-in-badge admin-users__logged-in-badge--yes"
          :title="formatFullDate(toAdminUser(row).lastLogin)"
        >
          Yes
        </span>
        <span v-else class="admin-users__logged-in-badge">No</span>
        <span v-if="toAdminUser(row).hasLoggedIn && toAdminUser(row).lastLogin" class="admin-users__logged-in-date">
          {{ formatLoginDate(toAdminUser(row).lastLogin) }}
        </span>
      </div>
    </template>
    <template #cell-actions="{ row }">
      <div class="admin-users__row-actions" @click.stop>
        <button
          v-if="isStudentMode"
          type="button"
          class="btn btn-sm"
          :class="toAdminUser(row).groupId ? 'btn-outline' : 'btn-primary'"
          :title="toAdminUser(row).groupId ? 'Remove from group' : 'Assign to a group'"
          @click="emit('group-action', toAdminUser(row))"
        >
          {{ toAdminUser(row).groupId ? 'Remove' : 'Assign' }}
        </button>
        <button type="button" class="btn btn-sm btn-outline" @click="emit('edit', toAdminUser(row))">
          Edit
        </button>
        <button
          type="button"
          class="btn btn-sm"
          :class="toAdminUser(row).isActive ? 'btn-outline' : 'btn-primary'"
          :title="toAdminUser(row).isActive ? 'Deactivate account' : 'Activate account'"
          @click="emit('toggle-active', toAdminUser(row))"
        >
          {{ toAdminUser(row).isActive ? 'Deactivate' : 'Activate' }}
        </button>
      </div>
    </template>
  </AdminDataTable>
</template>

<script setup lang="ts">
import AdminDataTable, { type AdminColumn, type SortState } from '@/components/admin/AdminDataTable.vue'
import type { AdminUser } from '@/utils/adminAPI'
import {
  formatFullDate,
  formatLoginDate,
  labelizeCountry,
  labelizeState,
  roleLabel,
  toAdminUser,
  userName,
  visibleInterests
} from '@/utils/userFormat'

defineProps<{
  columns: AdminColumn[]
  rows: AdminUser[]
  loading?: boolean
  selected?: Array<string | number>
  sortState?: SortState
  page?: number
  limit?: number
  totalCount?: number
  emptyMessage?: string
  isStudentMode: boolean
  pageSizeOptions?: number[]
  pagerLabel?: string
  selectAllLabel?: string
}>()

const emit = defineEmits<{
  (e: 'update:selected', value: Array<string | number>): void
  (e: 'update:sort', value: SortState): void
  (e: 'page-change', page: number): void
  (e: 'page-size-change', size: number): void
  (e: 'row-click', row: Record<string, unknown>): void
  (e: 'view', user: AdminUser): void
  (e: 'edit', user: AdminUser): void
  (e: 'group-action', user: AdminUser): void
  (e: 'toggle-active', user: AdminUser): void
}>()
</script>

<style scoped>
.admin-users__name-btn {
  border: none;
  background: transparent;
  padding: 0;
  font: inherit;
  font-weight: 600;
  color: var(--charcoal);
  text-align: left;
  cursor: pointer;
  transition: color 0.15s ease;
}

.admin-users__name-btn:hover {
  color: var(--dark-green);
  text-decoration: underline;
}

.admin-users__email {
  color: var(--text-muted);
}

.admin-users__student-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.1rem;
}

.admin-users__interests {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.3rem;
}

.admin-users__interest-chip {
  padding: 0.15rem 0.5rem;
  border: 1px solid var(--border-light);
  border-radius: 999px;
  background-color: var(--light-green);
  font-size: 0.8rem;
  white-space: nowrap;
}

.admin-users__interest-more {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.admin-users__role-badge,
.admin-users__status-badge {
  display: inline-block;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  background-color: var(--light-green);
  color: var(--dark-green);
  text-transform: capitalize;
}

.admin-users__status-badge--inactive {
  background-color: var(--bg-light);
  color: var(--text-muted);
}

.admin-users__logged-in {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.admin-users__logged-in-badge {
  display: inline-block;
  width: fit-content;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  background-color: var(--bg-light);
  color: var(--text-muted);
  text-transform: capitalize;
}

.admin-users__logged-in-badge--yes {
  background-color: rgba(16, 185, 129, 0.12);
  color: #047857;
}

.admin-users__logged-in-date {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.admin-users__row-actions {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}
</style>