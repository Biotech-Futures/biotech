<template>
  <div class="content-area admin-role-tasks">
    <div class="admin-role-tasks__header">
      <h1 class="admin-role-tasks__title">Role Tasks</h1>
      <p class="admin-role-tasks__subtitle">
        Defined once per role — every current and future holder picks it up automatically.
        Editing one here changes it for everyone; there is no per-user row to edit.
        For a task assigned to one person or a whole group, see
        <RouterLink to="/admin/tasks">Tasks</RouterLink>.
      </p>
    </div>

    <div class="admin-role-tasks__main">
      <div class="admin-role-tasks__table-toolbar">
        <button type="button" class="btn btn-primary" :disabled="loading || saving || taskActionBusy" @click="openCreate">
          <i class="fas fa-plus" aria-hidden="true"></i>
          <span>Add Role Task</span>
        </button>
      </div>

      <p v-if="error" class="admin-role-tasks__error" role="alert">
        <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
        <span>{{ error }}</span>
      </p>

      <BulkActionsBar
        v-if="selectedIds.length"
        :count="selectedIds.length"
        noun="role task"
        :disabled="taskActionBusy"
        @clear="clearSelection"
      >
        <button type="button" class="btn btn-sm btn-danger" :disabled="taskActionBusy" @click="openBulkDelete">
          Delete
        </button>
      </BulkActionsBar>

      <AdminDataTable
        :columns="columns"
        :rows="tableRows"
        row-key="id"
        :loading="loading"
        selectable
        :selected="selectedIds"
        :sort-state="sortState"
        :show-pagination="true"
        :page="page"
        :page-size="limit"
        :total-count="totalCount"
        :page-size-options="PAGE_SIZE_OPTIONS"
        empty-message="No role tasks found."
        pager-label="Role tasks pagination"
        select-all-label="Select all role tasks on this page"
        @update:selected="onSelectedChange"
        @update:sort="onSortChange"
        @page-change="onPageChange"
        @page-size-change="onPageSizeChange"
      >
        <template #cell-name="{ row }">
          <div class="admin-role-tasks__primary">
            <strong>{{ toRoleTask(row).name }}</strong>
            <span v-if="toRoleTask(row).description">{{ toRoleTask(row).description }}</span>
          </div>
        </template>

        <template #cell-role="{ row }">
          <span class="admin-role-tasks__badge">{{ toRoleTask(row).role?.roleName ?? '-' }}</span>
        </template>

        <template #cell-due="{ row }">
          {{ formatDueDate(toRoleTask(row).due_date) }}
        </template>

        <template #cell-actions="{ row }">
          <div class="admin-role-tasks__row-actions">
            <button
              type="button"
              class="btn btn-sm btn-outline"
              :disabled="loading || saving || taskActionBusy"
              @click.stop="openEdit(toRoleTask(row))"
            >
              Edit
            </button>
            <button
              type="button"
              class="btn btn-sm btn-outline"
              :disabled="loading || saving || taskActionBusy"
              @click.stop="openSingleDelete(toRoleTask(row))"
            >
              Delete
            </button>
          </div>
        </template>
      </AdminDataTable>

      <AdminRoleTaskFormSheet
        v-model="formOpen"
        :role-task="editingRoleTask"
        :roles="roles"
        :busy="saving"
        :submit-error="formError"
        @save="onFormSave"
      />

      <ConfirmDialog
        v-model="singleDeleteConfirmOpen"
        title="Delete role task"
        :message="singleDeleteMessage"
        confirm-label="Delete"
        variant="danger"
        :busy="taskActionBusy"
        @confirm="confirmSingleDelete"
        @cancel="cancelSingleDelete"
      >
        <p v-if="singleDeleteError" class="admin-role-tasks__dialog-error" role="alert">
          {{ singleDeleteError }}
        </p>
      </ConfirmDialog>

      <ConfirmDialog
        v-model="bulkDeleteConfirmOpen"
        title="Delete selected role tasks"
        :message="bulkDeleteMessage"
        confirm-label="Delete"
        variant="danger"
        :busy="taskActionBusy"
        @confirm="confirmBulkDelete"
        @cancel="bulkDeleteConfirmOpen = false"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AdminDataTable, {
  type AdminColumn,
  type SortState
} from '@/components/admin/AdminDataTable.vue'
import BulkActionsBar from '@/components/admin/BulkActionsBar.vue'
import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import AdminRoleTaskFormSheet from '@/components/admin/tasks/AdminRoleTaskFormSheet.vue'
import {
  createAdminRoleTask,
  deleteAdminRoleTask,
  fetchAdminEventMetaRoles,
  fetchAdminRoleTasks,
  updateAdminRoleTask,
  type AdminRoleTask,
  type AdminRoleTaskSortBy,
  type CreateAdminRoleTaskPayload,
  type UpdateAdminRoleTaskPayload
} from '@/utils/adminAPI'
import { logApiError } from '@/utils/apiError'
import { formatDateAU } from '@/utils/date'

const PAGE_SIZE_OPTIONS = [25, 50, 100]

type RoleOption = { id?: number; roleName: string }

const columns: AdminColumn[] = [
  { key: 'name', label: 'Name', sortable: true },
  { key: 'role', label: 'Role', sortable: true },
  { key: 'due', label: 'Due', sortable: true },
  { key: 'actions', label: 'Actions', align: 'right' }
]

const roleTasks = ref<AdminRoleTask[]>([])
const totalCount = ref(0)
const page = ref(1)
const limit = ref(25)
const selectedIds = ref<Array<string | number>>([])
const loading = ref(false)
const saving = ref(false)
const taskActionBusy = ref(false)
const error = ref('')
const formError = ref('')
const sortState = ref<SortState>({ key: 'due', direction: 'asc' })
const formOpen = ref(false)
const editingRoleTask = ref<AdminRoleTask | null>(null)
const roles = ref<RoleOption[]>([])
const selectedRoleTasks = ref(new Map<string | number, AdminRoleTask>())
const singleDeleteConfirmOpen = ref(false)
const roleTaskPendingDelete = ref<AdminRoleTask | null>(null)
const singleDeleteError = ref('')
const bulkDeleteConfirmOpen = ref(false)

const tableRows = computed(() => roleTasks.value as unknown as Record<string, unknown>[])
const selectedRoleTaskList = computed(() =>
  selectedIds.value
    .map((id) => selectedRoleTasks.value.get(id))
    .filter((roleTask): roleTask is AdminRoleTask => Boolean(roleTask))
)
const singleDeleteMessage = computed(() => {
  const roleTask = roleTaskPendingDelete.value
  return roleTask
    ? `Delete "${roleTask.name}"? Every current holder of the ${roleTask.role?.roleName ?? 'role'} role loses it. This cannot be undone.`
    : 'Delete this role task? This cannot be undone.'
})
const bulkDeleteMessage = computed(() =>
  `Delete ${selectedIds.value.length} selected role task${selectedIds.value.length === 1 ? '' : 's'}? This cannot be undone.`
)

const toRoleTask = (row: Record<string, unknown>) => row as unknown as AdminRoleTask

const normalizeRoles = (data: unknown): RoleOption[] => {
  const rows =
    Array.isArray(data)
      ? data
      : data && typeof data === 'object' && Array.isArray((data as { data?: unknown }).data)
        ? (data as { data: unknown[] }).data
        : []
  const result: RoleOption[] = []
  rows.forEach((role) => {
    if (!role || typeof role !== 'object') return
    const value = role as { id?: unknown; roleName?: unknown; role_name?: unknown }
    const roleName = typeof value.roleName === 'string'
      ? value.roleName
      : typeof value.role_name === 'string'
        ? value.role_name
        : ''
    if (!roleName) return
    result.push({
      id: typeof value.id === 'number' ? value.id : undefined,
      roleName
    })
  })
  return result
}

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const data = await fetchAdminRoleTasks({
      page: page.value,
      limit: limit.value,
      sortBy: sortState.value.key as AdminRoleTaskSortBy,
      sortOrder: sortState.value.direction
    })
    roleTasks.value = data.items
    totalCount.value = data.total
    if (selectedIds.value.length) {
      const next = new Map(selectedRoleTasks.value)
      data.items.forEach((roleTask) => {
        if (selectedIds.value.includes(roleTask.id)) next.set(roleTask.id, roleTask)
      })
      selectedRoleTasks.value = next
    }
  } catch (loadError) {
    logApiError('admin.role-tasks.list', loadError)
    error.value = loadError instanceof Error ? loadError.message : 'Role tasks could not be loaded right now.'
    roleTasks.value = []
    totalCount.value = 0
  } finally {
    loading.value = false
  }
}

const reloadFromFirstPage = () => {
  page.value = 1
  void load()
}

const clearSelection = () => {
  selectedIds.value = []
  selectedRoleTasks.value = new Map()
}

const clampPageAfterDelete = (deletedCount: number) => {
  if (deletedCount <= 0) return
  const nextTotal = Math.max(0, totalCount.value - deletedCount)
  const maxPage = Math.max(1, Math.ceil(nextTotal / limit.value))
  if (page.value > maxPage) page.value = maxPage
}

const loadOptions = async () => {
  try {
    const roleData = await fetchAdminEventMetaRoles()
    roles.value = normalizeRoles(roleData)
  } catch (optionsError) {
    logApiError('admin.role-tasks.options', optionsError)
    error.value =
      optionsError instanceof Error
        ? optionsError.message
        : 'Role options could not be loaded right now.'
    roles.value = []
  }
}

const openCreate = () => {
  editingRoleTask.value = null
  formError.value = ''
  formOpen.value = true
}

const openEdit = (roleTask: AdminRoleTask) => {
  editingRoleTask.value = roleTask
  formError.value = ''
  formOpen.value = true
}

const updateSelectedRoleTaskSnapshots = (ids: Array<string | number>) => {
  const next = new Map(selectedRoleTasks.value)
  const visibleRoleTasks = new Map(roleTasks.value.map((roleTask) => [roleTask.id, roleTask]))
  ids.forEach((id) => {
    const roleTask = visibleRoleTasks.get(Number(id)) ?? visibleRoleTasks.get(id as number)
    if (roleTask) next.set(id, roleTask)
  })
  Array.from(next.keys()).forEach((id) => {
    if (!ids.includes(id)) next.delete(id)
  })
  selectedRoleTasks.value = next
}

const onFormSave = async (payload: CreateAdminRoleTaskPayload | UpdateAdminRoleTaskPayload) => {
  if (saving.value) return
  saving.value = true
  formError.value = ''
  try {
    if (editingRoleTask.value) {
      await updateAdminRoleTask(editingRoleTask.value.id, payload as UpdateAdminRoleTaskPayload)
    } else {
      await createAdminRoleTask(payload as CreateAdminRoleTaskPayload)
    }
    formOpen.value = false
    editingRoleTask.value = null
    await load()
  } catch (saveError) {
    logApiError('admin.role-tasks.save', saveError)
    formError.value = saveError instanceof Error ? saveError.message : 'Role task could not be saved.'
  } finally {
    saving.value = false
  }
}

const updateSelectionAfterSuccess = (doneIds: Array<string | number>) => {
  const done = new Set(doneIds.map(String))
  selectedIds.value = selectedIds.value.filter((id) => !done.has(String(id)))
  const next = new Map(selectedRoleTasks.value)
  Array.from(next.keys()).forEach((id) => {
    if (done.has(String(id))) next.delete(id)
  })
  selectedRoleTasks.value = next
}

const openSingleDelete = (roleTask: AdminRoleTask) => {
  roleTaskPendingDelete.value = roleTask
  singleDeleteError.value = ''
  singleDeleteConfirmOpen.value = true
}

const cancelSingleDelete = () => {
  roleTaskPendingDelete.value = null
  singleDeleteError.value = ''
}

const confirmSingleDelete = async () => {
  if (!roleTaskPendingDelete.value || taskActionBusy.value) return
  const roleTask = roleTaskPendingDelete.value
  taskActionBusy.value = true
  error.value = ''
  try {
    await deleteAdminRoleTask(roleTask.id)
    singleDeleteConfirmOpen.value = false
    roleTaskPendingDelete.value = null
    singleDeleteError.value = ''
    updateSelectionAfterSuccess([roleTask.id])
    clampPageAfterDelete(1)
    await load()
  } catch (deleteError) {
    logApiError('admin.role-tasks.delete', deleteError)
    singleDeleteError.value = deleteError instanceof Error ? deleteError.message : 'Role task could not be deleted.'
  } finally {
    taskActionBusy.value = false
  }
}

const openBulkDelete = () => {
  bulkDeleteConfirmOpen.value = true
}

const confirmBulkDelete = async () => {
  const targets = selectedRoleTaskList.value
  if (!targets.length || taskActionBusy.value) {
    bulkDeleteConfirmOpen.value = false
    return
  }
  taskActionBusy.value = true
  error.value = ''
  try {
    const outcomes = await Promise.allSettled(
      targets.map((roleTask) => deleteAdminRoleTask(roleTask.id).then(() => roleTask.id))
    )
    const doneIds = outcomes
      .filter((outcome): outcome is PromiseFulfilledResult<number> => outcome.status === 'fulfilled')
      .map((outcome) => outcome.value)
    updateSelectionAfterSuccess(doneIds)
    bulkDeleteConfirmOpen.value = false
    clampPageAfterDelete(doneIds.length)
    await load()
    const failed = targets.length - doneIds.length
    error.value = failed
      ? doneIds.length
        ? `Deleted ${doneIds.length}, but ${failed} could not be deleted.`
        : 'Unable to delete the selected role tasks.'
      : ''
  } finally {
    taskActionBusy.value = false
  }
}

const onSortChange = (next: SortState) => {
  sortState.value = next
  clearSelection()
  reloadFromFirstPage()
}

const onPageChange = (next: number) => {
  page.value = next
  clearSelection()
  void load()
}

const onPageSizeChange = (size: number) => {
  limit.value = size
  clearSelection()
  reloadFromFirstPage()
}

const onSelectedChange = (value: Array<string | number>) => {
  selectedIds.value = value
  updateSelectedRoleTaskSnapshots(value)
}

const formatDueDate = (value: string | null) => value ? formatDateAU(value) : '-'

onMounted(() => {
  void load()
  void loadOptions()
})
</script>

<style scoped>
.admin-role-tasks__header {
  margin-bottom: 1.5rem;
}

.admin-role-tasks__title {
  margin: 0 0 0.25rem;
}

.admin-role-tasks__subtitle {
  margin: 0;
  color: var(--text-muted);
}

.admin-role-tasks__main {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.admin-role-tasks__table-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 0.75rem;
}

.admin-role-tasks__table-toolbar .btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.admin-role-tasks__row-actions {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.4rem;
}

.admin-role-tasks__error {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0;
  padding: 0.75rem 1rem;
  border-left: 4px solid var(--danger);
  border-radius: 6px;
  background-color: rgba(220, 53, 69, 0.08);
  color: var(--danger);
}

.admin-role-tasks__dialog-error {
  margin: 0.9rem 0 0;
  padding: 0.65rem 0.75rem;
  border-left: 3px solid var(--danger);
  border-radius: 6px;
  background-color: rgba(220, 53, 69, 0.08);
  color: var(--danger);
  font-size: 0.9rem;
  line-height: 1.4;
}

.admin-role-tasks__primary {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.admin-role-tasks__primary strong,
.admin-role-tasks__primary span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.admin-role-tasks__primary span {
  color: var(--text-muted);
}

.admin-role-tasks__badge {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0.2rem 0.55rem;
  border: 1px solid var(--border-light);
  border-radius: 999px;
  background-color: var(--bg-light);
  color: var(--text-muted);
  font-size: 0.75rem;
  font-weight: 600;
}

@media (max-width: 640px) {
  .admin-role-tasks__table-toolbar .btn {
    justify-content: center;
    width: 100%;
  }
}
</style>
