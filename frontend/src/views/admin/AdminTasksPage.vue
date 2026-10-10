<template>
  <div class="content-area admin-tasks">
    <header class="page-header">
      <h1 class="page-title">Tasks</h1>
      <p class="page-subtitle">Assign and track admin-managed tasks.</p>
    </header>

    <div class="admin-tasks__main">
      <p v-if="error" class="admin-tasks__error" role="alert">
        <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
        <span>{{ error }}</span>
      </p>

      <BulkActionsBar
        v-if="selectedIds.length"
        :count="selectedIds.length"
        noun="task"
        :disabled="taskActionBusy"
        @clear="clearSelection"
      >
        <label class="admin-tasks__bulk-status" for="task-bulk-status">
          <span class="sr-only">Set selected task status</span>
          <select
            id="task-bulk-status"
            value=""
            :disabled="taskActionBusy"
            @change="onBulkStatusChange"
          >
            <option value="" disabled>Set status</option>
            <option v-for="status in TASK_STATUSES" :key="status" :value="status">
              {{ taskStatusLabel(status) }}
            </option>
          </select>
        </label>
        <button type="button" class="btn btn-sm btn-danger" :disabled="taskActionBusy" @click="openBulkDelete">
          Delete
        </button>
      </BulkActionsBar>

      <AppDataTable
        :columns="columns"
        :rows="tableRows"
        row-key="id"
        :loading="loading"
        :selected="selectedIds"
        :sort="sortState"
        :page="page"
        :page-size="limit"
        :total-count="totalCount"
        v-model:search="searchInput"
        search-placeholder="Name or description"
        two-line-rows
        empty-message="No tasks found."
        :action-columns="2"
        @update:selected="onSelectedChange"
        @update:sort="onSortChange"
        @update:page="onPageChange"
        @update:page-size="onPageSizeChange"
      >
        <!-- Type, beside Search. -->
        <template #filters>
          <div class="admin-tasks__filter">
            <label class="admin-tasks__filter-label" for="task-type-filter">Type</label>
            <select
              id="task-type-filter"
              :value="taskTypeFilter"
              :disabled="loading || taskActionBusy"
              @change="onTaskTypeChange"
            >
              <option value="all">All</option>
              <option value="group">Group</option>
              <option value="individual">Individual</option>
            </select>
          </div>
        </template>
        <template #search-side>
          <button
            type="button"
            class="btn btn-primary admin-tasks__add"
            :disabled="loading || saving || taskActionBusy"
            @click="openCreate"
          >
            <i class="fas fa-plus" aria-hidden="true"></i>
            <span>Add Task</span>
          </button>
        </template>

        <template #cell-name="{ row }">
          <div class="admin-tasks__primary">
            <strong>{{ toTask(row).name }}</strong>
            <span v-if="toTask(row).description">{{ toTask(row).description }}</span>
          </div>
        </template>

        <template #cell-type="{ row }">
          {{ taskTypeLabel(toTask(row).task_type) }}
        </template>

        <template #cell-target="{ row }">
          {{ targetLabel(toTask(row)) }}
        </template>

        <template #cell-status="{ row }">
          <span
            class="admin-tasks__status"
            :class="`admin-tasks__status--${toTask(row).status}`"
          >
            {{ taskStatusLabel(toTask(row).status) }}
          </span>
        </template>

        <template #cell-due="{ row }">
          {{ formatDueDate(toTask(row).due_date) }}
        </template>

        <!-- Edit | Delete, each in its own column. -->
        <template #actions="{ row, column }">
          <button
            v-if="column === 0"
            type="button"
            class="btn btn-sm btn-outline"
            :disabled="loading || saving || taskActionBusy"
            @click.stop="openEdit(toTask(row))"
          >
            Edit
          </button>
          <button
            v-else
            type="button"
            class="btn btn-sm btn-outline"
            :disabled="loading || saving || taskActionBusy"
            @click.stop="openSingleDelete(toTask(row))"
          >
            Delete
          </button>
        </template>
      </AppDataTable>

      <AdminTaskFormSheet
        v-model="formOpen"
        :task="editingTask"
        :groups="groups"
        :users="users"
        :roles="roles"
        :busy="saving"
        :submit-error="formError"
        @save="onFormSave"
      />

      <ConfirmDialog
        v-model="roleFanoutConfirmOpen"
        title="Create role tasks"
        :message="roleFanoutConfirmMessage"
        confirm-label="Create tasks"
        variant="warning"
        :busy="saving"
        @confirm="confirmRoleFanoutCreate"
        @cancel="cancelRoleFanoutCreate"
      />

      <ConfirmDialog
        v-model="singleDeleteConfirmOpen"
        title="Delete task"
        :message="singleDeleteMessage"
        confirm-label="Delete"
        variant="danger"
        :busy="taskActionBusy"
        @confirm="confirmSingleDelete"
        @cancel="cancelSingleDelete"
      >
        <p v-if="singleDeleteError" class="admin-tasks__dialog-error" role="alert">
          {{ singleDeleteError }}
        </p>
      </ConfirmDialog>

      <ConfirmDialog
        v-model="bulkDeleteConfirmOpen"
        title="Delete selected tasks"
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
import { computed, onMounted, ref, watch } from 'vue'
import AppDataTable, { type DataTableColumn, type DataTableSort } from '@/components/AppDataTable.vue'
import BulkActionsBar from '@/components/admin/BulkActionsBar.vue'
import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import AdminTaskFormSheet from '@/components/admin/tasks/AdminTaskFormSheet.vue'
import {
  createAdminTask,
  deleteAdminTask,
  fetchAdminEventMetaRoles,
  fetchAdminGroupList,
  fetchAdminTasks,
  fetchAdminUsers,
  updateAdminTask,
  type AdminGroup,
  type AdminTask,
  type AdminTaskSortBy,
  type AdminTaskStatus,
  type AdminTaskType,
  type AdminUser,
  type CreateAdminTaskPayload,
  type UpdateAdminTaskPayload
} from '@/utils/adminAPI'
import { logApiError } from '@/utils/apiError'
import { DATA_TABLE_TWO_LINE_ROW_HEIGHT, fitPageSize, serverPageLimit } from '@/utils/dataTable'
import { formatDateAU } from '@/utils/date'


type TaskTypeFilter = 'all' | AdminTaskType
type RoleOption = { id?: number; roleName: string }

const TASK_STATUS_LABELS: Record<AdminTaskStatus, string> = {
  todo: 'To Do',
  in_progress: 'In Progress',
  done: 'Done',
  blocked: 'Blocked'
}
const TASK_STATUSES = Object.keys(TASK_STATUS_LABELS) as AdminTaskStatus[]

const columns: DataTableColumn[] = [
  { key: 'name', label: 'Name', sortable: true },
  { key: 'type', label: 'Type', sortable: true },
  { key: 'target', label: 'Target', sortable: true },
  { key: 'status', label: 'Status', sortable: true },
  { key: 'due', label: 'Due', sortable: true }
]

const tasks = ref<AdminTask[]>([])
const totalCount = ref(0)
const page = ref(1)
const limit = ref(fitPageSize(DATA_TABLE_TWO_LINE_ROW_HEIGHT))
const taskTypeFilter = ref<TaskTypeFilter>('all')
const searchInput = ref('')
let searchTimer: ReturnType<typeof setTimeout> | null = null
const selectedIds = ref<Array<string | number>>([])
const loading = ref(false)
const saving = ref(false)
const taskActionBusy = ref(false)
const error = ref('')
const formError = ref('')
const sortState = ref<DataTableSort>({ key: 'due', direction: 'asc' })
const formOpen = ref(false)
const editingTask = ref<AdminTask | null>(null)
const groups = ref<AdminGroup[]>([])
const users = ref<AdminUser[]>([])
const roles = ref<RoleOption[]>([])
const roleFanoutConfirmOpen = ref(false)
const pendingRoleFanoutPayload = ref<CreateAdminTaskPayload | null>(null)
const pendingRoleFanoutRecipientCount = ref<number | null>(null)
const selectedTasks = ref(new Map<string | number, AdminTask>())
const singleDeleteConfirmOpen = ref(false)
const taskPendingDelete = ref<AdminTask | null>(null)
const singleDeleteError = ref('')
const bulkDeleteConfirmOpen = ref(false)

const tableRows = computed(() => tasks.value as unknown as Record<string, unknown>[])
const selectedTaskList = computed(() =>
  selectedIds.value
    .map((id) => selectedTasks.value.get(id))
    .filter((task): task is AdminTask => Boolean(task))
)
const roleFanoutConfirmMessage = computed(() => {
  const payload = pendingRoleFanoutPayload.value
  const role = payload?.assigned_role ?? 'selected'
  const count = pendingRoleFanoutRecipientCount.value
  const recipientText = count === 1
    ? '1 recipient will receive this task.'
    : typeof count === 'number'
      ? `${count} recipients will each receive a separate task.`
      : 'Each recipient will receive a separate task.'
  return `Create a separate task for every user with the ${role} role? ${recipientText} There is no single action to undo this assignment.`
})
const singleDeleteMessage = computed(() => {
  const task = taskPendingDelete.value
  return task
    ? `Delete "${task.name}"? This cannot be undone.`
    : 'Delete this task? This cannot be undone.'
})
const bulkDeleteMessage = computed(() =>
  `Delete ${selectedIds.value.length} selected task${selectedIds.value.length === 1 ? '' : 's'}? This cannot be undone.`
)

const toTask = (row: Record<string, unknown>) => row as unknown as AdminTask

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const data = await fetchAdminTasks({
      page: page.value,
      limit: serverPageLimit(limit.value),
      task_type: taskTypeFilter.value === 'all' ? undefined : taskTypeFilter.value,
      search: searchInput.value.trim() || undefined,
      sortBy: sortState.value.key as AdminTaskSortBy,
      sortOrder: sortState.value.direction
    })
    tasks.value = data.items
    totalCount.value = data.total
    if (selectedIds.value.length) {
      const next = new Map(selectedTasks.value)
      data.items.forEach((task) => {
        if (selectedIds.value.includes(task.id)) next.set(task.id, task)
      })
      selectedTasks.value = next
    }
  } catch (loadError) {
    logApiError('admin.tasks.list', loadError)
    error.value = loadError instanceof Error ? loadError.message : 'Tasks could not be loaded right now.'
    tasks.value = []
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
  selectedTasks.value = new Map()
}

const clampPageAfterDelete = (deletedCount: number) => {
  if (deletedCount <= 0) return
  const nextTotal = Math.max(0, totalCount.value - deletedCount)
  const maxPage = Math.max(1, Math.ceil(nextTotal / limit.value))
  if (page.value > maxPage) page.value = maxPage
}

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

const loadOptions = async () => {
  try {
    const [groupData, userData, roleData] = await Promise.all([
      fetchAdminGroupList({ page: 1, limit: 200 }),
      fetchAdminUsers({ page: 1, limit: 200, sortBy: 'name', sortOrder: 'asc' }),
      fetchAdminEventMetaRoles()
    ])
    groups.value = groupData.items.map((group) => ({
      id: group.id,
      name: group.name
    }))
    users.value = userData.items
    roles.value = normalizeRoles(roleData)
  } catch (optionsError) {
    logApiError('admin.tasks.options', optionsError)
    error.value =
      optionsError instanceof Error
        ? optionsError.message
        : 'Task assignment options could not be loaded right now.'
    groups.value = []
    users.value = []
    roles.value = []
  }
}

const openCreate = () => {
  editingTask.value = null
  formError.value = ''
  formOpen.value = true
}

const openEdit = (task: AdminTask) => {
  editingTask.value = task
  formError.value = ''
  formOpen.value = true
}

const updateSelectedTaskSnapshots = (ids: Array<string | number>) => {
  const next = new Map(selectedTasks.value)
  const visibleTasks = new Map(tasks.value.map((task) => [task.id, task]))
  ids.forEach((id) => {
    const task = visibleTasks.get(Number(id)) ?? visibleTasks.get(id as number)
    if (task) next.set(id, task)
  })
  Array.from(next.keys()).forEach((id) => {
    if (!ids.includes(id)) next.delete(id)
  })
  selectedTasks.value = next
}

const saveTask = async (payload: CreateAdminTaskPayload | UpdateAdminTaskPayload) => {
  saving.value = true
  formError.value = ''
  try {
    if (editingTask.value) {
      await updateAdminTask(editingTask.value.id, payload as UpdateAdminTaskPayload)
    } else {
      await createAdminTask(payload as CreateAdminTaskPayload)
    }
    formOpen.value = false
    editingTask.value = null
    await load()
  } catch (saveError) {
    logApiError('admin.tasks.save', saveError)
    formError.value = saveError instanceof Error ? saveError.message : 'Task could not be saved.'
  } finally {
    saving.value = false
  }
}

const onFormSave = async (
  payload: CreateAdminTaskPayload | UpdateAdminTaskPayload,
  recipientCount?: number | null
) => {
  if (saving.value) return
  if (!editingTask.value && 'assigned_role' in payload && payload.assigned_role) {
    pendingRoleFanoutPayload.value = payload
    pendingRoleFanoutRecipientCount.value = recipientCount ?? null
    roleFanoutConfirmOpen.value = true
    return
  }

  await saveTask(payload)
}

const cancelRoleFanoutCreate = () => {
  pendingRoleFanoutPayload.value = null
  pendingRoleFanoutRecipientCount.value = null
}

const confirmRoleFanoutCreate = async () => {
  if (!pendingRoleFanoutPayload.value) return
  const payload = pendingRoleFanoutPayload.value
  pendingRoleFanoutPayload.value = null
  pendingRoleFanoutRecipientCount.value = null
  roleFanoutConfirmOpen.value = false
  await saveTask(payload)
}

const updateSelectionAfterSuccess = (doneIds: Array<string | number>) => {
  const done = new Set(doneIds.map(String))
  selectedIds.value = selectedIds.value.filter((id) => !done.has(String(id)))
  const next = new Map(selectedTasks.value)
  Array.from(next.keys()).forEach((id) => {
    if (done.has(String(id))) next.delete(id)
  })
  selectedTasks.value = next
}

const reportBulkResult = (
  verb: 'Deleted' | 'Updated',
  doneCount: number,
  totalCountForAction: number,
  fallback: string
) => {
  const failed = totalCountForAction - doneCount
  if (failed === 0) {
    error.value = ''
    return
  }
  error.value = doneCount
    ? `${verb} ${doneCount}, but ${failed} could not be ${verb.toLowerCase()}.`
    : fallback
}

const openSingleDelete = (task: AdminTask) => {
  taskPendingDelete.value = task
  singleDeleteError.value = ''
  singleDeleteConfirmOpen.value = true
}

const cancelSingleDelete = () => {
  taskPendingDelete.value = null
  singleDeleteError.value = ''
}

const confirmSingleDelete = async () => {
  if (!taskPendingDelete.value || taskActionBusy.value) return
  const task = taskPendingDelete.value
  taskActionBusy.value = true
  error.value = ''
  try {
    await deleteAdminTask(task.id)
    singleDeleteConfirmOpen.value = false
    taskPendingDelete.value = null
    singleDeleteError.value = ''
    updateSelectionAfterSuccess([task.id])
    clampPageAfterDelete(1)
    await load()
  } catch (deleteError) {
    logApiError('admin.tasks.delete', deleteError)
    singleDeleteError.value = deleteError instanceof Error ? deleteError.message : 'Task could not be deleted.'
  } finally {
    taskActionBusy.value = false
  }
}

const openBulkDelete = () => {
  bulkDeleteConfirmOpen.value = true
}

const confirmBulkDelete = async () => {
  const targets = selectedTaskList.value
  if (!targets.length || taskActionBusy.value) {
    bulkDeleteConfirmOpen.value = false
    return
  }
  taskActionBusy.value = true
  error.value = ''
  try {
    const outcomes = await Promise.allSettled(
      targets.map((task) => deleteAdminTask(task.id).then(() => task.id))
    )
    const doneIds = outcomes
      .filter((outcome): outcome is PromiseFulfilledResult<number> => outcome.status === 'fulfilled')
      .map((outcome) => outcome.value)
    updateSelectionAfterSuccess(doneIds)
    bulkDeleteConfirmOpen.value = false
    clampPageAfterDelete(doneIds.length)
    await load()
    reportBulkResult('Deleted', doneIds.length, targets.length, 'Unable to delete the selected tasks.')
  } finally {
    taskActionBusy.value = false
  }
}

const updateTaskStatusPayload = (task: AdminTask, status: AdminTaskStatus): UpdateAdminTaskPayload => ({
  name: task.name,
  description: task.description,
  due_date: task.due_date,
  status,
  parent: task.parent
})

const onBulkStatusChange = async (event: Event) => {
  const select = event.target as HTMLSelectElement
  const status = select.value as AdminTaskStatus
  select.value = ''
  if (!status || taskActionBusy.value) return
  const targets = selectedTaskList.value
  if (!targets.length) return

  taskActionBusy.value = true
  error.value = ''
  try {
    const outcomes = await Promise.allSettled(
      targets.map((task) =>
        updateAdminTask(task.id, updateTaskStatusPayload(task, status)).then(() => task.id)
      )
    )
    const doneIds = outcomes
      .filter((outcome): outcome is PromiseFulfilledResult<number> => outcome.status === 'fulfilled')
      .map((outcome) => outcome.value)
    updateSelectionAfterSuccess(doneIds)
    await load()
    reportBulkResult('Updated', doneIds.length, targets.length, 'Unable to update the selected tasks.')
  } finally {
    taskActionBusy.value = false
  }
}

// A pause in typing searches again from the first page.
watch(searchInput, () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    clearSelection()
    reloadFromFirstPage()
  }, 350)
})

const onTaskTypeChange = (event: Event) => {
  taskTypeFilter.value = (event.target as HTMLSelectElement).value as TaskTypeFilter
  clearSelection()
  reloadFromFirstPage()
}

const onSortChange = (next: DataTableSort) => {
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
  updateSelectedTaskSnapshots(value)
}

const taskTypeLabel = (type: AdminTaskType) => type === 'group' ? 'Group' : 'Individual'

const taskStatusLabel = (status: AdminTaskStatus) => TASK_STATUS_LABELS[status] ?? status

const targetLabel = (task: AdminTask) => {
  if (task.task_type === 'group') return task.group ? `Group #${task.group}` : '-'
  return task.assigned_user ? `User #${task.assigned_user}` : '-'
}

const formatDueDate = (value: string | null) => value ? formatDateAU(value) : '-'

onMounted(() => {
  void load()
  void loadOptions()
})
</script>

<style scoped>
.admin-tasks__main {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.admin-tasks__add {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

/* Type, in the table's search card, drawn like Search. */
.admin-tasks__filter {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.admin-tasks__filter-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.admin-tasks__filter select {
  min-width: 9rem;
  padding: 0.45rem 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  font-size: 0.9rem;
  font-family: inherit;
  background-color: var(--surface-elevated);
  color: var(--teal);
}

.admin-tasks__bulk-status select {
  min-width: 140px;
  height: 2rem;
  padding: 0.25rem 0.5rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background-color: var(--white);
  color: var(--teal);
  font: inherit;
}

.admin-tasks__bulk-status select:disabled {
  background-color: var(--bg-light);
  color: var(--text-muted);
  cursor: not-allowed;
}

.admin-tasks__error {
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

.admin-tasks__dialog-error {
  margin: 0.9rem 0 0;
  padding: 0.65rem 0.75rem;
  border-left: 3px solid var(--danger);
  border-radius: 6px;
  background-color: rgba(220, 53, 69, 0.08);
  color: var(--danger);
  font-size: 0.9rem;
  line-height: 1.4;
}

.admin-tasks__selection {
  margin: 0;
  padding: 0.6rem 1rem;
  border: 1px solid var(--border-light);
  border-left: 3px solid var(--dark-green);
  border-radius: 8px;
  background-color: var(--light-green);
  color: var(--teal);
  font-weight: 600;
}

.admin-tasks__primary {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.admin-tasks__primary span,
.admin-tasks__muted {
  color: var(--text-muted);
}

/* Status as coloured text. */
.admin-tasks__status--todo {
  color: var(--text-muted);
}

.admin-tasks__status--in_progress {
  color: var(--dark-green);
}

.admin-tasks__status--done {
  color: var(--success);
}

.admin-tasks__status--blocked {
  color: var(--danger);
}
</style>
