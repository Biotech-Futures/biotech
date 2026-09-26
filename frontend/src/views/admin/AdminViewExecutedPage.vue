<template>
  <div class="content-area admin-view-executed">
    <button type="button" class="btn btn-outline back-button" @click="goBack">
      <i class="fas fa-arrow-left" aria-hidden="true"></i> Back to Views
    </button>

    <div v-if="loading && !view" class="detail-state" role="status" aria-live="polite">
      <span class="loading"></span>
      <span>Loading view...</span>
    </div>

    <div v-else-if="error && !view" class="card detail-state detail-state-error">
      <h3>View unavailable</h3>
      <p>{{ error }}</p>
      <button type="button" class="btn btn-primary" @click="reload">Retry</button>
    </div>

    <template v-else-if="view">
      <header class="detail-header">
        <div>
          <h1>{{ view.name }}</h1>
          <div class="admin-view-executed__meta">
            <span
              class="admin-view-executed__badge"
              :class="{ 'admin-view-executed__badge--default': view.isDefault }"
            >
              {{ badgeLabel }}
            </span>
            <span class="admin-view-executed__count">
              {{ totalCount }} {{ totalCount === 1 ? 'user' : 'users' }}
            </span>
          </div>
        </div>
      </header>

      <p v-if="error" class="admin-view-executed__error" role="alert">
        <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
        <span>{{ error }}</span>
      </p>

      <div class="admin-view-executed__controls">
        <div class="admin-view-executed__search">
          <i class="fas fa-magnifying-glass admin-view-executed__search-icon" aria-hidden="true"></i>
          <input
            v-model="searchInput"
            type="search"
            class="admin-view-executed__search-input"
            placeholder="Name or email"
            aria-label="Search users"
          />
        </div>

        <div class="admin-view-executed__group-by">
          <label class="admin-view-executed__group-by-label" for="view-group-by">Group by</label>
          <select
            id="view-group-by"
            :value="groupBy"
            @change="onGroupByChange(($event.target as HTMLSelectElement).value as GroupByOption)"
          >
            <option value="none">None</option>
            <option value="role">Role</option>
            <option value="status">Status</option>
          </select>
          <span v-if="groupBy !== 'none'" class="admin-view-executed__group-by-hint">
            Grouping is not yet applied server-side; results are shown sorted, not grouped.
          </span>
        </div>
      </div>

      <BulkActionsBar
        v-if="bulkCount && !loading"
        :count="bulkCount"
        noun="user"
        :disabled="busy"
        @clear="clearSelection"
      >
        <AdminViewBulkBar
          :busy="busy"
          :can-assign="canAssignToGroup"
          @assign="openBatchAssign"
          @activate="confirmBulkStatus(true)"
          @deactivate="confirmBulkStatus(false)"
          @delete="confirmBulkDelete"
        />
      </BulkActionsBar>

      <AdminViewResultsTable
        :columns="columns"
        :rows="rows"
        :loading="loading"
        :selected="selectedIds"
        :sort-state="sortState"
        :page="page"
        :limit="limit"
        :total-count="totalCount"
        :page-size-options="pageSizeOptions"
        :empty-message="emptyMessage"
        @update:selected="onSelectedChange"
        @update:sort="onSortChange"
        @page-change="onPageChange"
        @page-size-change="onPageSizeChange"
        @row-click="onRowClick"
        @view="openView"
        @edit="openEdit"
        @toggle-active="onToggleActive"
      />
    </template>

    <!-- Bulk activate/deactivate confirm -->
    <ConfirmDialog
      v-model="bulkStatus.open"
      :title="bulkStatus.title"
      :message="bulkStatus.message"
      :confirm-label="bulkStatus.confirmLabel"
      :variant="bulkStatus.action === 'deactivate' ? 'warning' : 'default'"
      :busy="busy"
      @confirm="runBulkStatus"
    />

    <!-- Bulk delete confirm -->
    <ConfirmDialog
      v-model="bulkDelete.open"
      title="Delete users"
      :message="bulkDeleteMessage"
      confirm-label="Delete"
      variant="danger"
      :busy="busy"
      :disabled="deleteConfirmBlocked"
      @confirm="runBulkDelete"
    >
      <label class="admin-view-executed__force-toggle">
        <input v-model="bulkForce" type="checkbox" />
        <span>
          Force delete — also permanently delete each user's chat messages, uploaded resources,
          workshops, and match runs. Required to remove accounts that have any activity.
        </span>
      </label>
      <p v-if="bulkForce" class="admin-view-executed__force-warning">
        This destroys their content for everyone, not just the account, and cannot be undone.
      </p>
      <div v-if="bulkForce" class="admin-view-executed__delete-type">
        <label class="admin-view-executed__delete-label" for="bulk-delete-confirm">
          Type <span class="admin-view-executed__delete-keyword">DELETE</span> to confirm
        </label>
        <input
          id="bulk-delete-confirm"
          v-model="deleteConfirmText"
          class="form-input"
          autocomplete="off"
          placeholder="DELETE"
        />
      </div>
    </ConfirmDialog>

    <!-- Single deactivate confirm -->
    <ConfirmDialog
      v-model="singleToggle.open"
      title="Deactivate user"
      :message="singleToggle.message"
      confirm-label="Deactivate"
      variant="warning"
      :busy="busy"
      @confirm="runSingleToggle"
    />

    <!-- Single delete confirm (reachable from the edit sheet's Delete button) -->
    <ConfirmDialog
      v-model="singleDelete.open"
      title="Delete user"
      :message="singleDelete.message"
      confirm-label="Delete"
      variant="danger"
      :busy="busy"
      :disabled="singleDeleteConfirmBlocked"
      @confirm="onSingleDeleteConfirmed"
    >
      <label class="admin-view-executed__force-toggle">
        <input v-model="singleDelete.force" type="checkbox" />
        <span>
          Force delete — also permanently delete this user's chat messages, uploaded resources,
          workshops, and match runs. Required to remove accounts that have any activity.
        </span>
      </label>
      <p v-if="singleDelete.force" class="admin-view-executed__force-warning">
        This destroys their content for everyone, not just the account, and cannot be undone.
      </p>
      <div v-if="singleDelete.force" class="admin-view-executed__delete-type">
        <label class="admin-view-executed__delete-label" for="single-delete-confirm">
          Type <span class="admin-view-executed__delete-keyword">DELETE</span> to confirm
        </label>
        <input
          id="single-delete-confirm"
          v-model="singleDeleteConfirmText"
          class="form-input"
          autocomplete="off"
          placeholder="DELETE"
        />
      </div>
    </ConfirmDialog>

    <!-- Assign selected users to a group -->
    <StudentAssignDialog v-model:open="assignOpen" :students="assignStudents" @confirmed="onAssignConfirmed" />

    <!-- Edit sheet -->
    <AdminUserFormSheet
      v-model="formOpen"
      :user="formEditUser"
      user-noun="user"
      :is-supervisor-mode="false"
      :countries="countries"
      :states="states"
      :supervisors="supervisors"
      :busy="busy"
      @saved="onFormSaved"
      @delete="confirmEditorDelete"
    />

    <!-- View detail sheet -->
    <AdminUserDetailSheet :open="viewOpen" :user="detailUser" @close="onViewClose" @edit="openEditFromView" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BulkActionsBar from '@/components/admin/BulkActionsBar.vue'
import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import StudentAssignDialog from '@/components/admin/StudentAssignDialog.vue'
import AdminUserDetailSheet from '@/components/admin/users/AdminUserDetailSheet.vue'
import AdminUserFormSheet from '@/components/admin/users/AdminUserFormSheet.vue'
import AdminViewBulkBar from '@/components/admin/views/AdminViewBulkBar.vue'
import AdminViewResultsTable from '@/components/admin/views/AdminViewResultsTable.vue'
import {
  useAdminViewExecuted,
  type GroupByOption,
  type ViewResultRow
} from '@/composables/admin/useAdminViewExecuted'

const route = useRoute()
const router = useRouter()

const viewId = computed(() => Number(route.params.id))

const {
  view,
  rows,
  totalCount,
  loading,
  busy,
  error,
  page,
  limit,
  sortState,
  groupBy,
  searchInput,
  columns,
  emptyMessage,
  badgeLabel,
  pageSizeOptions,
  reload,
  loadResults,
  onSortChange,
  onPageChange,
  onPageSizeChange,
  onGroupByChange,
  selectedIds,
  bulkCount,
  canAssignToGroup,
  clearSelection,
  onSelectedChange,
  viewOpen,
  detailUser,
  openView,
  onViewClose,
  onRowClick,
  singleToggle,
  onToggleActive,
  runSingleToggle,
  singleDelete,
  singleDeleteConfirmText,
  singleDeleteConfirmBlocked,
  runSingleDelete,
  bulkStatus,
  confirmBulkStatus,
  runBulkStatus,
  bulkDelete,
  bulkForce,
  deleteConfirmText,
  bulkDeleteMessage,
  deleteConfirmBlocked,
  confirmBulkDelete,
  runBulkDelete,
  assignOpen,
  assignStudents,
  openBatchAssign,
  onAssignConfirmed,
  countries,
  states,
  supervisors,
  init
} = useAdminViewExecuted(viewId)

const goBack = (): void => {
  router.push('/admin/views')
}

// Create/edit sheet state (the sheet owns the form itself); deleting from the
// editor routes through the composable's shared single-delete confirm.
const formOpen = ref(false)
const formEditUser = ref<ViewResultRow | null>(null)

const openEdit = (user: ViewResultRow): void => {
  formEditUser.value = user
  formOpen.value = true
}

const openEditFromView = (): void => {
  const user = detailUser.value
  if (!user) return
  onViewClose()
  openEdit(user)
}

const onFormSaved = (): void => {
  void loadResults()
}

const confirmEditorDelete = (): void => {
  const user = formEditUser.value
  if (!user) return
  singleDelete.value = {
    open: true,
    userId: user.id,
    message: 'This permanently removes the account and all related data. This cannot be undone.',
    force: false
  }
  singleDeleteConfirmText.value = ''
}

const onSingleDeleteConfirmed = (): void => {
  formOpen.value = false
  void runSingleDelete()
}

watch(viewId, reload, { immediate: true })
onMounted(() => {
  void init()
})
</script>

<style scoped>
.back-button {
  align-items: center;
  display: inline-flex;
  gap: 0.45rem;
  margin-bottom: 1rem;
}

.detail-state {
  align-items: center;
  display: flex;
  gap: 0.75rem;
}

.detail-state-error {
  align-items: flex-start;
  border-left: 4px solid var(--danger);
  flex-direction: column;
}

.detail-header {
  align-items: flex-start;
  display: flex;
  gap: 1.25rem;
  justify-content: space-between;
  margin-bottom: 1.25rem;
}

.detail-header h1 {
  margin-bottom: 0.35rem;
}

.admin-view-executed__meta {
  align-items: center;
  display: flex;
  gap: 0.65rem;
}

.admin-view-executed__badge {
  background-color: var(--light-green);
  border-radius: 999px;
  color: var(--dark-green);
  display: inline-block;
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.2rem 0.55rem;
}

.admin-view-executed__badge--default {
  background-color: rgba(26, 52, 94, 0.1);
  color: var(--navy);
}

.admin-view-executed__count {
  color: var(--text-muted);
  font-size: 0.85rem;
}

.admin-view-executed__error {
  align-items: center;
  color: var(--danger);
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.admin-view-executed__controls {
  align-items: flex-end;
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  justify-content: space-between;
  margin-bottom: 1rem;
}

.admin-view-executed__search {
  align-items: center;
  display: flex;
  max-width: 320px;
  position: relative;
  width: 100%;
}

.admin-view-executed__search-icon {
  color: var(--text-muted);
  left: 0.75rem;
  position: absolute;
}

.admin-view-executed__search-input {
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 0.5rem 0.75rem 0.5rem 2.25rem;
  width: 100%;
}

.admin-view-executed__group-by {
  align-items: center;
  display: flex;
  gap: 0.5rem;
}

.admin-view-executed__group-by-label {
  color: var(--charcoal);
  font-size: 0.85rem;
  font-weight: 600;
}

.admin-view-executed__group-by select {
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 0.4rem 0.6rem;
}

.admin-view-executed__group-by-hint {
  color: var(--text-muted);
  font-size: 0.75rem;
  font-style: italic;
  max-width: 220px;
}

.admin-view-executed__force-toggle {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: var(--charcoal);
}

.admin-view-executed__force-toggle input {
  margin-top: 0.15rem;
  accent-color: var(--danger);
}

.admin-view-executed__force-warning {
  margin: 0.5rem 0 0;
  padding: 0.55rem 0.7rem;
  border-left: 4px solid var(--danger);
  border-radius: 6px;
  background-color: rgba(220, 53, 69, 0.08);
  color: var(--danger);
  font-size: 0.8rem;
}

.admin-view-executed__delete-type {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  margin-top: 0.75rem;
}

.admin-view-executed__delete-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.admin-view-executed__delete-keyword {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-weight: 700;
  color: var(--danger);
}

.admin-view-executed__delete-type input {
  padding: 0.5rem 0.7rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--white);
  color: var(--charcoal);
  font: inherit;
}
</style>
