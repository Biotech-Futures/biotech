<template>
  <div class="admin-users">
    <!-- Top actions: search + add (supervisors) or import/add (students) -->
    <AdminUsersToolbar
      :is-supervisor-mode="isSupervisorMode"
      :is-student-mode="isStudentMode"
      :add-label="addLabel"
      :loading="loading"
      v-model:search="searchInput"
      @add="openCreate"
      @import-students="openStudentImport"
    />

    <!-- Users tab filters: search / role / country / state / in-group / status -->
    <AdminUsersFilters
      v-if="!isSupervisorMode"
      :filters="filters"
      v-model:search="searchInput"
      :is-student-mode="isStudentMode"
      :is-role-fixed="isRoleFixed"
      :filter-countries="filterCountries"
      :states="states"
      @patch="applyFilterPatch"
    />

    <p v-if="error" class="admin-users__error" role="alert">
      <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
      <span>{{ error }}</span>
    </p>

    <!-- Bulk actions bar -->
    <BulkActionsBar
      v-if="bulkCount && !loading"
      :count="bulkCount"
      :noun="userNoun"
      :disabled="busy"
      @clear="clearSelection"
    >
      <AdminUsersBulkBar
        :busy="busy"
        :is-student-mode="isStudentMode"
        :is-supervisor-mode="isSupervisorMode"
        :select-all-matching="selectAllMatching"
        :group-actions-hint="groupActionsHint"
        :remove-group-actions-hint="removeGroupActionsHint"
        :grouped-count="groupedCount"
        :plural-noun="pluralNoun"
        @assign="openBatchAssign"
        @remove="openBatchRemove"
        @activate="confirmBulkStatus(true)"
        @deactivate="confirmBulkStatus(false)"
        @delete="confirmBulkDelete"
      />
    </BulkActionsBar>

    <!-- Selection banner: "all matching" state / "select all matching" offer -->
    <div v-if="selectionBanner" class="admin-users__selection-banner" aria-live="polite">
      <template v-if="selectAllMatching">
        <span>
          <i class="fas fa-check-double admin-users__selection-icon" aria-hidden="true"></i>
          <span v-if="excludedCount > 0">
            {{ effectiveSelectAllCount }} of {{ totalCount }} {{ pluralNoun }} selected.
          </span>
          <span v-else>All {{ totalCount }} {{ pluralNoun }} matching these filters are selected.</span>
        </span>
        <button type="button" class="admin-users__selection-link" @click="clearSelection">
          Clear selection
        </button>
      </template>
      <template v-else>
        <span>
          <i class="fas fa-circle-info admin-users__selection-icon" aria-hidden="true"></i>
          <span>All {{ pageRows }} {{ pluralNoun }} on this page are selected.</span>
        </span>
        <button type="button" class="admin-users__selection-link" @click="selectAllMatchingNow">
          Select all {{ totalCount }} {{ pluralNoun }} matching these filters
        </button>
      </template>
    </div>

    <AdminUsersTable
      :columns="columns"
      :rows="rows"
      :loading="loading"
      :selected="displaySelected"
      :sort-state="sortState"
      :page="page"
      :limit="limit"
      :total-count="totalCount"
      :empty-message="emptyMessage"
      :is-student-mode="isStudentMode"
      :page-size-options="PAGE_SIZE_OPTIONS"
      pager-label="Users pagination"
      :select-all-label="`Select all ${pluralNoun} on this page`"
      @view="openView"
      @edit="openEdit"
      @group-action="onGroupAction"
      @toggle-active="onToggleActive"
      @update:selected="onSelectedChange"
      @update:sort="onSortChange"
      @page-change="onPageChange"
      @page-size-change="onPageSizeChange"
      @row-click="onRowClick"
    />

    <!-- Bulk status confirm -->
    <ConfirmDialog
      v-model="bulkStatus.open"
      :title="bulkStatus.title"
      :message="bulkStatus.message"
      :confirm-label="bulkStatus.confirmLabel"
      :variant="bulkStatus.action === 'deactivate' ? 'warning' : 'default'"
      :busy="busy"
      @confirm="runBulkStatus"
    />

    <!-- Bulk delete confirm (forces the DELETE keyword when select-all / force) -->
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
      <label class="admin-users__force-toggle">
        <input v-model="bulkForce" type="checkbox" />
        <span>
          Force delete — also permanently delete each user's chat messages, uploaded resources,
          workshops, and match runs. Required to remove accounts that have any activity.
        </span>
      </label>
      <p v-if="bulkForce" class="admin-users__force-warning">
        This destroys their content for everyone, not just the account, and cannot be undone.
      </p>
      <div class="admin-users__delete-type">
        <label class="admin-users__filter-label" for="bulk-delete-confirm">
          Type <span class="admin-users__delete-keyword">DELETE</span> to confirm
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

    <!-- Single delete confirm (row action or from the editor) -->
    <ConfirmDialog
      v-model="singleDelete.open"
      title="Delete user"
      :message="singleDelete.message"
      confirm-label="Delete"
      variant="danger"
      :busy="busy"
      @confirm="onSingleDeleteConfirmed"
    />

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

    <!-- Assign student(s) to a group (single + batch share this surface) -->
    <StudentAssignDialog
      v-model:open="assignOpen"
      :students="assignStudents"
      @confirmed="onAssignConfirmed"
    />

    <!-- Single remove-from-group confirm -->
    <ConfirmDialog
      v-model="singleRemove.open"
      title="Remove from group"
      :message="singleRemove.message"
      confirm-label="Remove"
      variant="danger"
      :busy="busy"
      @confirm="runSingleRemove"
    />

    <!-- Batch remove-from-group confirm -->
    <ConfirmDialog
      v-model="batchRemoveConfirm.open"
      :title="batchRemoveTitle"
      :message="batchRemoveMessage"
      confirm-label="Remove"
      variant="danger"
      :busy="busy"
      @confirm="runBatchRemove"
    />

    <!-- Create / Edit sheet -->
    <AdminUserFormSheet
      v-model="formOpen"
      :user="formEditUser"
      :user-noun="userNoun"
      :fixed-role="fixedRole"
      :is-supervisor-mode="isSupervisorMode"
      :countries="countries"
      :states="states"
      :supervisors="supervisors"
      :busy="busy"
      @saved="onFormSaved"
      @delete="confirmEditorDelete"
    />

    <!-- View detail sheet -->
    <AdminUserDetailSheet
      :open="viewOpen"
      :user="detailUser"
      @close="onViewClose"
      @edit="openEditFromView"
    />

    <AdminStudentImportSheet
      v-if="isStudentMode"
      v-model="studentImportOpen"
      @imported="onStudentsImported"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, toRef } from 'vue'
import BulkActionsBar from '@/components/admin/BulkActionsBar.vue'
import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import StudentAssignDialog from '@/components/admin/StudentAssignDialog.vue'
import AdminUsersToolbar from '@/components/admin/users/AdminUsersToolbar.vue'
import AdminUsersFilters from '@/components/admin/users/AdminUsersFilters.vue'
import AdminUsersTable from '@/components/admin/users/AdminUsersTable.vue'
import AdminUsersBulkBar from '@/components/admin/users/AdminUsersBulkBar.vue'
import AdminUserFormSheet from '@/components/admin/users/AdminUserFormSheet.vue'
import AdminUserDetailSheet from '@/components/admin/users/AdminUserDetailSheet.vue'
import AdminStudentImportSheet from '@/components/admin/users/AdminStudentImportSheet.vue'
import type { AdminUser } from '@/utils/adminAPI'
import { PAGE_SIZE_OPTIONS } from '@/utils/userOptions'
import { useAdminUsersView } from '@/composables/admin/useAdminUsersView'

const props = withDefaults(
  defineProps<{
    title: string
    noun: string
    /** When set (e.g. 'supervisor'), the list is filtered to this role and the role cannot be changed. */
    roleFilter?: string
  }>(),
  {
    roleFilter: ''
  }
)

const {
  loading,
  busy,
  error,
  rows,
  totalCount,
  page,
  limit,
  sortState,
  countries,
  filterCountries,
  states,
  supervisors,
  searchInput,
  filters,
  columns,
  emptyMessage,
  selectAllMatching,
  excludedCount,
  effectiveSelectAllCount,
  bulkCount,
  groupedCount,
  selectionBanner,
  pageRows,
  singleToggle,
  singleDelete,
  bulkStatus,
  bulkDelete,
  bulkForce,
  deleteConfirmText,
  bulkDeleteMessage,
  deleteConfirmBlocked,
  assignOpen,
  assignStudents,
  singleRemove,
  batchRemoveConfirm,
  batchRemoveTitle,
  batchRemoveMessage,
  groupActionsHint,
  removeGroupActionsHint,
  viewOpen,
  detailUser,
  isStudentMode,
  isSupervisorMode,
  isRoleFixed,
  fixedRole,
  userNoun,
  pluralNoun,
  addLabel,
  displaySelected,
  applyFilterPatch,
  onSortChange,
  onPageChange,
  onPageSizeChange,
  onSelectedChange,
  clearSelection,
  selectAllMatchingNow,
  onRowClick,
  openView,
  onViewClose,
  onToggleActive,
  runSingleToggle,
  runSingleDelete,
  confirmBulkStatus,
  runBulkStatus,
  confirmBulkDelete,
  runBulkDelete,
  openBatchAssign,
  openBatchRemove,
  onAssignConfirmed,
  onGroupAction,
  runSingleRemove,
  runBatchRemove,
  load,
  init
} = useAdminUsersView({
  roleFilter: toRef(props, 'roleFilter'),
  noun: toRef(props, 'noun')
})

// Create / Edit form sheet state (the sheet owns the form itself).
const formOpen = ref(false)
const formEditUser = ref<AdminUser | null>(null)
const studentImportOpen = ref(false)

const openStudentImport = () => {
  if (!isStudentMode.value) return
  studentImportOpen.value = true
}

const onStudentsImported = () => {
  void load()
}

const openCreate = () => {
  formEditUser.value = null
  formOpen.value = true
}

const openEdit = (user: AdminUser) => {
  formEditUser.value = user
  formOpen.value = true
}

const openEditFromView = () => {
  const user = detailUser.value
  if (!user) return
  onViewClose()
  openEdit(user)
}

const onFormSaved = () => {
  void load()
}

// Deleting from the editor shares the single-delete confirm; the editor is
// closed first so a deletion doesn't leave a dangling (now-nonexistent) user.
const confirmEditorDelete = () => {
  const user = formEditUser.value
  if (!user) return
  singleDelete.value = {
    open: true,
    userId: user.id,
    message: 'This permanently removes the account and all related data. This cannot be undone.'
  }
}

const onSingleDeleteConfirmed = () => {
  formOpen.value = false
  void runSingleDelete()
}

onMounted(() => {
  void init()
})
</script>

<style scoped>
.admin-users {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.admin-users__error {
  margin: 0;
  padding: 0.7rem 0.9rem;
  border-left: 4px solid var(--danger);
  border-radius: 6px;
  background-color: rgba(220, 53, 69, 0.08);
  color: var(--danger);
  font-size: 0.875rem;
}

.admin-users__selection-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
  padding: 0.7rem 1rem;
  border: 1px solid rgba(1, 113, 81, 0.25);
  border-radius: 8px;
  background-color: rgba(1, 113, 81, 0.06);
  color: var(--charcoal);
  font-size: 0.875rem;
}

.admin-users__selection-icon {
  margin-right: 0.4rem;
  color: var(--dark-green);
}

.admin-users__selection-link {
  border: none;
  background: none;
  padding: 0;
  font: inherit;
  color: var(--dark-green);
  font-weight: 600;
  text-decoration: underline;
  cursor: pointer;
}

.admin-users__force-toggle {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: var(--charcoal);
}

.admin-users__force-toggle input {
  margin-top: 0.15rem;
  accent-color: var(--danger);
}

.admin-users__force-warning {
  margin: 0.5rem 0 0;
  padding: 0.55rem 0.7rem;
  border-left: 4px solid var(--danger);
  border-radius: 6px;
  background-color: rgba(220, 53, 69, 0.08);
  color: var(--risk);
  font-size: 0.8rem;
}

.admin-users__delete-type {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  margin-top: 0.75rem;
}

.admin-users__filter-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.admin-users__delete-keyword {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-weight: 700;
  color: var(--danger);
}

.admin-users__delete-type input {
  padding: 0.5rem 0.7rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--white);
  color: var(--charcoal);
  font: inherit;
}
</style>
