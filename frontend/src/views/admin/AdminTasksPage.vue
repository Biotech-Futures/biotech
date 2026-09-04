<template>
  <div class="content-area admin-tasks">
    <div class="admin-tasks__header">
      <h1 class="admin-tasks__title">Tasks</h1>
      <p class="admin-tasks__subtitle">Assign and track admin-managed tasks.</p>
    </div>

    <div class="admin-tasks__main">
      <div class="admin-tasks__table-toolbar">
        <label class="admin-tasks__filter" for="task-type-filter">
          <span>Type</span>
          <select
            id="task-type-filter"
            :value="taskTypeFilter"
            :disabled="loading"
            @change="onTaskTypeChange"
          >
            <option value="all">All</option>
            <option value="group">Group</option>
            <option value="individual">Individual</option>
          </select>
        </label>
        <button type="button" class="btn btn-primary" :disabled="loading || saving" @click="openCreate">
          <i class="fas fa-plus" aria-hidden="true"></i>
          <span>Add Task</span>
        </button>
      </div>

      <p v-if="error" class="admin-tasks__error" role="alert">
        <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
        <span>{{ error }}</span>
      </p>

      <p v-if="selectedIds.length" class="admin-tasks__selection" aria-live="polite">
        {{ selectedIds.length }} task{{ selectedIds.length === 1 ? '' : 's' }} selected
      </p>

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
        empty-message="No tasks found."
        pager-label="Tasks pagination"
        select-all-label="Select all tasks on this page"
        @update:selected="onSelectedChange"
        @update:sort="onSortChange"
        @page-change="onPageChange"
        @page-size-change="onPageSizeChange"
      >
        <template #cell-name="{ row }">
          <div class="admin-tasks__primary">
            <strong>{{ toTask(row).name }}</strong>
            <span v-if="toTask(row).description">{{ toTask(row).description }}</span>
          </div>
        </template>

        <template #cell-type="{ row }">
          <span class="admin-tasks__badge">{{ taskTypeLabel(toTask(row).task_type) }}</span>
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

        <template #cell-actions="{ row }">
          <button
            type="button"
            class="btn btn-sm btn-outline"
            :disabled="loading || saving"
            @click.stop="openEdit(toTask(row))"
          >
            Edit
          </button>
        </template>
      </AdminDataTable>

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
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AdminDataTable, {
  type AdminColumn,
  type SortState
} from '@/components/admin/AdminDataTable.vue'
import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import AdminTaskFormSheet from '@/components/admin/tasks/AdminTaskFormSheet.vue'
import {
  createAdminTask,
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
import { formatDateAU } from '@/utils/date'

const PAGE_SIZE_OPTIONS = [25, 50, 100]

type TaskTypeFilter = 'all' | AdminTaskType
type RoleOption = { id?: number; roleName: string }

const TASK_STATUS_LABELS: Record<AdminTaskStatus, string> = {
  todo: 'To Do',
  in_progress: 'In Progress',
  done: 'Done',
  blocked: 'Blocked'
}

const columns: AdminColumn[] = [
  { key: 'name', label: 'Name', sortable: true },
  { key: 'type', label: 'Type', sortable: true },
  { key: 'target', label: 'Target', sortable: true },
  { key: 'status', label: 'Status', sortable: true },
  { key: 'due', label: 'Due', sortable: true },
  { key: 'actions', label: 'Actions', align: 'right' }
]

const tasks = ref<AdminTask[]>([])
const totalCount = ref(0)
const page = ref(1)
const limit = ref(25)
const taskTypeFilter = ref<TaskTypeFilter>('all')
const selectedIds = ref<Array<string | number>>([])
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const formError = ref('')
const sortState = ref<SortState>({ key: 'due', direction: 'asc' })
const formOpen = ref(false)
const editingTask = ref<AdminTask | null>(null)
const groups = ref<AdminGroup[]>([])
const users = ref<AdminUser[]>([])
const roles = ref<RoleOption[]>([])
const roleFanoutConfirmOpen = ref(false)
const pendingRoleFanoutPayload = ref<CreateAdminTaskPayload | null>(null)
const pendingRoleFanoutRecipientCount = ref<number | null>(null)

const tableRows = computed(() => tasks.value as unknown as Record<string, unknown>[])
const roleFanoutConfirmMessage = computed(() => {
  const payload = pendingRoleFanoutPayload.value
  const role = payload?.assigned_role ?? 'selected'
  const count = pendingRoleFanoutRecipientCount.value
  const countText = typeof count === 'number'
    ? ` This will create ${count} separate task${count === 1 ? '' : 's'}.`
    : ''
  return `Create separate tasks for every user with the ${role} role?${countText} This cannot be undone in bulk.`
})

const toTask = (row: Record<string, unknown>) => row as unknown as AdminTask

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const data = await fetchAdminTasks({
      page: page.value,
      limit: limit.value,
      task_type: taskTypeFilter.value === 'all' ? undefined : taskTypeFilter.value,
      sortBy: sortState.value.key as AdminTaskSortBy,
      sortOrder: sortState.value.direction
    })
    tasks.value = data.items
    totalCount.value = data.total
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

const onTaskTypeChange = (event: Event) => {
  taskTypeFilter.value = (event.target as HTMLSelectElement).value as TaskTypeFilter
  clearSelection()
  reloadFromFirstPage()
}

const onSortChange = (next: SortState) => {
  sortState.value = next
  clearSelection()
  reloadFromFirstPage()
}

const onPageChange = (next: number) => {
  page.value = next
  void load()
}

const onPageSizeChange = (size: number) => {
  limit.value = size
  clearSelection()
  reloadFromFirstPage()
}

const onSelectedChange = (value: Array<string | number>) => {
  selectedIds.value = value
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
.admin-tasks__header {
  margin-bottom: 1.5rem;
}

.admin-tasks__title {
  margin: 0 0 0.25rem;
}

.admin-tasks__subtitle {
  margin: 0;
  color: var(--text-muted);
}

.admin-tasks__main {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.admin-tasks__table-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.admin-tasks__table-toolbar .btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.admin-tasks__filter {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--text-muted);
  font-size: 0.9rem;
  font-weight: 600;
}

.admin-tasks__filter select {
  min-width: 160px;
  height: 2rem;
  padding: 0.25rem 0.5rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background-color: var(--white);
  color: var(--charcoal);
}

@media (max-width: 640px) {
  .admin-tasks__table-toolbar {
    align-items: stretch;
  }

  .admin-tasks__filter {
    justify-content: space-between;
    width: 100%;
  }

  .admin-tasks__filter select {
    flex: 1;
  }

  .admin-tasks__table-toolbar .btn {
    justify-content: center;
    width: 100%;
  }
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

.admin-tasks__selection {
  margin: 0;
  padding: 0.6rem 1rem;
  border: 1px solid var(--border-light);
  border-left: 3px solid var(--dark-green);
  border-radius: 8px;
  background-color: var(--light-green);
  color: var(--charcoal);
  font-weight: 600;
}

.admin-tasks__primary {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.admin-tasks__primary strong,
.admin-tasks__primary span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.admin-tasks__primary span,
.admin-tasks__muted {
  color: var(--text-muted);
}

.admin-tasks__badge,
.admin-tasks__status {
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

.admin-tasks__status--todo {
  border-color: var(--border-light);
  color: var(--text-muted);
}

.admin-tasks__status--in_progress {
  border-color: rgba(1, 113, 81, 0.3);
  background-color: rgba(1, 113, 81, 0.08);
  color: var(--dark-green);
}

.admin-tasks__status--done {
  border-color: rgba(40, 167, 69, 0.35);
  background-color: rgba(40, 167, 69, 0.08);
  color: var(--success);
}

.admin-tasks__status--blocked {
  border-color: rgba(220, 53, 69, 0.35);
  background-color: rgba(220, 53, 69, 0.08);
  color: var(--danger);
}
</style>
