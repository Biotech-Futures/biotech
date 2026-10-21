<template>
  <div class="content-area admin-plan">
    <header class="page-header">
      <h1 class="page-title">Group Plans</h1>
      <p class="page-subtitle">
        Build the shared plan every group works through: stages, then the tasks inside them.
      </p>
    </header>

    <div class="admin-plan__main">
      <p v-if="error" class="admin-plan__error" role="alert">
        <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
        <span>{{ error }}</span>
      </p>

      <div class="admin-plan__grid">
        <!-- Stages -->
        <section class="admin-plan__stages" aria-label="Stages">
          <header class="admin-plan__panel-header">
            <h2 class="admin-plan__panel-title">Stages</h2>
            <button
              type="button"
              class="btn btn-sm btn-primary"
              :disabled="busy"
              @click="openCreateStage"
            >
              <i class="fas fa-plus" aria-hidden="true"></i>
              <span>Add Stage</span>
            </button>
          </header>

          <ul class="admin-plan__stage-list">
            <li
              v-for="stage in stages"
              :key="stage.id"
              class="admin-plan__stage"
              :class="{ 'admin-plan__stage--active': stage.id === selectedStageId }"
            >
              <button
                type="button"
                class="admin-plan__stage-select"
                :aria-pressed="stage.id === selectedStageId"
                @click="selectStage(stage.id)"
              >
                <span class="admin-plan__stage-name">{{ stage.name }}</span>
                <span class="admin-plan__stage-meta">
                  {{ stageTaskCount(stage.id) }} task{{ stageTaskCount(stage.id) === 1 ? '' : 's' }}
                </span>
              </button>
              <div class="admin-plan__stage-actions">
                <button
                  type="button"
                  class="btn btn-sm btn-outline"
                  :disabled="busy"
                  @click.stop="openEditStage(stage)"
                >
                  Edit
                </button>
                <button
                  type="button"
                  class="btn btn-sm btn-outline"
                  :disabled="busy"
                  @click.stop="openDeleteStage(stage)"
                >
                  Delete
                </button>
              </div>
            </li>
            <li v-if="!loadingStages && !stages.length" class="admin-plan__empty">
              No stages yet. Add one to start building the plan.
            </li>
          </ul>
        </section>

        <!-- Tasks -->
        <section class="admin-plan__tasks" aria-label="Tasks">
          <template v-if="stages.length">
            <AppDataTable
              :columns="columns"
              :rows="tableRows"
              row-key="id"
              :loading="loadingTasks"
              :selectable="false"
              :sort="sortState"
              :page="page"
              :page-size="limit"
              :total-count="totalCount"
              two-line-rows
              empty-message="No tasks in the plan yet."
              :action-columns="2"
              @update:sort="onSortChange"
              @update:page="onPageChange"
              @update:page-size="onPageSizeChange"
            >
              <template #filters>
                <div class="admin-plan__filter">
                  <label class="admin-plan__filter-label" for="plan-stage-filter">Stage</label>
                  <AppSelect
                    id="plan-stage-filter"
                    :model-value="selectedStageId"
                    :options="stageFilterOptions"
                    :disabled="loadingTasks || busy"
                    @change="onStageFilterChange"
                  />
                </div>
              </template>
              <template #search-side>
                <button
                  type="button"
                  class="btn btn-primary admin-plan__add"
                  :disabled="loadingTasks || busy"
                  @click="openCreateTask"
                >
                  <i class="fas fa-plus" aria-hidden="true"></i>
                  <span>Add Task</span>
                </button>
              </template>

              <template #cell-name="{ row }">
                <div class="admin-plan__primary">
                  <strong>{{ toTask(row).name }}</strong>
                  <span v-if="toTask(row).description">{{ toTask(row).description }}</span>
                </div>
              </template>

              <template #cell-stage="{ row }">
                {{ stageName(toTask(row).stage_id) }}
              </template>

              <template #cell-audience="{ row }">
                {{ audienceLabel(toTask(row).audience_role) }}
              </template>

              <template #cell-mode="{ row }">
                {{ modeLabel(toTask(row).completion_mode) }}
                <i
                  v-if="toTask(row).has_completions"
                  class="fas fa-lock admin-plan__lock"
                  title="Audience and mode are locked: a group has recorded this task"
                  aria-hidden="true"
                ></i>
              </template>

              <template #cell-due="{ row }">
                {{ formatPlanDate(toTask(row).due_date) }}
              </template>

              <template #actions="{ row, column }">
                <button
                  v-if="column === 0"
                  type="button"
                  class="btn btn-sm btn-outline"
                  :disabled="loadingTasks || busy"
                  @click.stop="openEditTask(toTask(row))"
                >
                  Edit
                </button>
                <button
                  v-else
                  type="button"
                  class="btn btn-sm btn-outline"
                  :disabled="loadingTasks || busy"
                  @click.stop="openDeleteTask(toTask(row))"
                >
                  Delete
                </button>
              </template>
            </AppDataTable>
          </template>

          <p v-else-if="!loadingStages" class="admin-plan__empty admin-plan__empty--panel" role="status">
            Create a stage first, then add tasks to it.
          </p>
        </section>
      </div>

      <AdminPlanStageFormSheet
        v-model="stageFormOpen"
        :stage="editingStage"
        :next-position="stages.length"
        :busy="busy"
        :submit-error="stageFormError"
        @save="onStageSave"
      />

      <AdminPlanTaskFormSheet
        v-model="taskFormOpen"
        :task="editingTask"
        :stages="stages"
        :default-stage-id="defaultStageId"
        :busy="busy"
        :submit-error="taskFormError"
        @save="onTaskSave"
      />

      <ConfirmDialog
        v-model="deleteStageConfirmOpen"
        title="Delete stage"
        :message="deleteStageMessage"
        confirm-label="Delete"
        variant="danger"
        :busy="busy"
        @confirm="confirmDeleteStage"
        @cancel="cancelDeleteStage"
      >
        <p v-if="deleteStageError" class="admin-plan__dialog-error" role="alert">
          {{ deleteStageError }}
        </p>
      </ConfirmDialog>

      <ConfirmDialog
        v-model="deleteTaskConfirmOpen"
        title="Delete task"
        :message="deleteTaskMessage"
        confirm-label="Delete"
        variant="danger"
        :busy="busy"
        @confirm="confirmDeleteTask"
        @cancel="cancelDeleteTask"
      >
        <p v-if="deleteTaskError" class="admin-plan__dialog-error" role="alert">
          {{ deleteTaskError }}
        </p>
      </ConfirmDialog>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AppDataTable, { type DataTableColumn, type DataTableSort } from '@/components/AppDataTable.vue'
import AppSelect, { type AppSelectOption, type AppSelectValue } from '@/components/AppSelect.vue'
import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import AdminPlanStageFormSheet from '@/components/admin/plans/AdminPlanStageFormSheet.vue'
import AdminPlanTaskFormSheet from '@/components/admin/plans/AdminPlanTaskFormSheet.vue'
import {
  createAdminPlanStage,
  createAdminPlanTask,
  deleteAdminPlanStage,
  deleteAdminPlanTask,
  fetchAdminPlanStages,
  fetchAdminPlanTasks,
  updateAdminPlanStage,
  updateAdminPlanTask,
  type AdminPlanAudienceRole,
  type AdminPlanCompletionMode,
  type AdminPlanStage,
  type AdminPlanStagePayload,
  type AdminPlanTask,
  type AdminPlanTaskPayload,
  type AdminPlanTaskSortBy
} from '@/utils/adminAPI'
import { logApiError } from '@/utils/apiError'
import { DATA_TABLE_TWO_LINE_ROW_HEIGHT, fitPageSize, serverPageLimit } from '@/utils/dataTable'
import { formatShortDate } from '@/utils/date'

const ALL_STAGES = 'all'

const AUDIENCE_LABELS: Record<AdminPlanAudienceRole, string> = {
  student: 'Students',
  mentor: 'Mentors',
  supervisor: 'Supervisors'
}
const MODE_LABELS: Record<AdminPlanCompletionMode, string> = {
  per_person: 'Each person',
  per_group: 'Whole group'
}

const columns: DataTableColumn[] = [
  { key: 'name', label: 'Name', sortable: true },
  { key: 'stage', label: 'Stage', sortable: false },
  { key: 'audience', label: 'Audience', sortable: false },
  { key: 'mode', label: 'Completion', sortable: false },
  { key: 'due', label: 'Due', sortable: true }
]

const stages = ref<AdminPlanStage[]>([])
const tasks = ref<AdminPlanTask[]>([])
const totalCount = ref(0)
const page = ref(1)
const limit = ref(fitPageSize(DATA_TABLE_TWO_LINE_ROW_HEIGHT))
const selectedStageId = ref<number | string>(ALL_STAGES)
const sortState = ref<DataTableSort>({ key: 'position', direction: 'asc' })

const loadingStages = ref(false)
const loadingTasks = ref(false)
const busy = ref(false)
const error = ref('')

const stageFormOpen = ref(false)
const editingStage = ref<AdminPlanStage | null>(null)
const stageFormError = ref('')

const taskFormOpen = ref(false)
const editingTask = ref<AdminPlanTask | null>(null)
const taskFormError = ref('')

const deleteStageConfirmOpen = ref(false)
const stagePendingDelete = ref<AdminPlanStage | null>(null)
const deleteStageError = ref('')

const deleteTaskConfirmOpen = ref(false)
const taskPendingDelete = ref<AdminPlanTask | null>(null)
const deleteTaskError = ref('')

const tableRows = computed(() => tasks.value as unknown as Record<string, unknown>[])
const toTask = (row: Record<string, unknown>) => row as unknown as AdminPlanTask

// The stage a new task is added to: the selected stage, or none when "All".
const defaultStageId = computed(() =>
  typeof selectedStageId.value === 'number' ? selectedStageId.value : null
)

const stageFilterOptions = computed<AppSelectOption[]>(() => [
  { value: ALL_STAGES, label: 'All stages' },
  ...stages.value.map((stage) => ({ value: stage.id, label: stage.name }))
])

const deleteStageMessage = computed(() => {
  const stage = stagePendingDelete.value
  return stage
    ? `Delete "${stage.name}"? A stage still holding tasks cannot be deleted.`
    : 'Delete this stage?'
})
const deleteTaskMessage = computed(() => {
  const task = taskPendingDelete.value
  return task
    ? `Delete "${task.name}"? This cannot be undone.`
    : 'Delete this task? This cannot be undone.'
})

const stageName = (stageId: number) =>
  stages.value.find((stage) => stage.id === stageId)?.name ?? '-'
const stageTaskCount = (stageId: number) =>
  tasks.value.filter((task) => task.stage_id === stageId).length
const audienceLabel = (role: AdminPlanAudienceRole) => AUDIENCE_LABELS[role] ?? role
const modeLabel = (mode: AdminPlanCompletionMode) => MODE_LABELS[mode] ?? mode
// A due date is a picked day stored as that day's UTC midnight.
const formatPlanDate = (value: string | null) => (value ? formatShortDate(value, 'UTC') : '-')

const loadStages = async () => {
  loadingStages.value = true
  try {
    stages.value = await fetchAdminPlanStages()
    if (
      selectedStageId.value !== ALL_STAGES &&
      !stages.value.some((stage) => String(stage.id) === String(selectedStageId.value))
    ) {
      selectedStageId.value = ALL_STAGES
    }
  } catch (loadError) {
    logApiError('admin.plan.stages', loadError)
    error.value = loadError instanceof Error ? loadError.message : 'Stages could not be loaded.'
    stages.value = []
  } finally {
    loadingStages.value = false
  }
}

const loadTasks = async () => {
  loadingTasks.value = true
  error.value = ''
  try {
    const data = await fetchAdminPlanTasks({
      page: page.value,
      limit: serverPageLimit(limit.value),
      sortBy: sortState.value.key as AdminPlanTaskSortBy,
      sortOrder: sortState.value.direction
    })
    tasks.value = data.items
    totalCount.value = data.total
  } catch (loadError) {
    logApiError('admin.plan.tasks', loadError)
    error.value = loadError instanceof Error ? loadError.message : 'Tasks could not be loaded.'
    tasks.value = []
    totalCount.value = 0
  } finally {
    loadingTasks.value = false
  }
}

const reloadTasksFromFirstPage = () => {
  page.value = 1
  void loadTasks()
}

const selectStage = (stageId: number) => {
  selectedStageId.value = selectedStageId.value === stageId ? ALL_STAGES : stageId
}

const onStageFilterChange = (value: AppSelectValue) => {
  selectedStageId.value = value === null ? ALL_STAGES : (value as number | string)
}

const onSortChange = (next: DataTableSort) => {
  sortState.value = next
  reloadTasksFromFirstPage()
}
const onPageChange = (next: number) => {
  page.value = next
  void loadTasks()
}
const onPageSizeChange = (size: number) => {
  limit.value = size
  reloadTasksFromFirstPage()
}

const clampPageAfterDelete = () => {
  const maxPage = Math.max(1, Math.ceil(Math.max(0, totalCount.value - 1) / limit.value))
  if (page.value > maxPage) page.value = maxPage
}

// Stages -------------------------------------------------------------------

const openCreateStage = () => {
  editingStage.value = null
  stageFormError.value = ''
  stageFormOpen.value = true
}
const openEditStage = (stage: AdminPlanStage) => {
  editingStage.value = stage
  stageFormError.value = ''
  stageFormOpen.value = true
}
const onStageSave = async (payload: AdminPlanStagePayload) => {
  busy.value = true
  stageFormError.value = ''
  try {
    if (editingStage.value) {
      await updateAdminPlanStage(editingStage.value.id, payload)
    } else {
      await createAdminPlanStage(payload)
    }
    stageFormOpen.value = false
    editingStage.value = null
    await loadStages()
  } catch (saveError) {
    logApiError('admin.plan.stage-save', saveError)
    stageFormError.value = saveError instanceof Error ? saveError.message : 'Stage could not be saved.'
  } finally {
    busy.value = false
  }
}
const openDeleteStage = (stage: AdminPlanStage) => {
  stagePendingDelete.value = stage
  deleteStageError.value = ''
  deleteStageConfirmOpen.value = true
}
const cancelDeleteStage = () => {
  stagePendingDelete.value = null
  deleteStageError.value = ''
}
const confirmDeleteStage = async () => {
  const stage = stagePendingDelete.value
  if (!stage || busy.value) return
  busy.value = true
  deleteStageError.value = ''
  try {
    await deleteAdminPlanStage(stage.id)
    deleteStageConfirmOpen.value = false
    stagePendingDelete.value = null
    if (String(selectedStageId.value) === String(stage.id)) selectedStageId.value = ALL_STAGES
    await loadStages()
    await loadTasks()
  } catch (deleteError) {
    logApiError('admin.plan.stage-delete', deleteError)
    deleteStageError.value =
      deleteError instanceof Error ? deleteError.message : 'Stage could not be deleted.'
  } finally {
    busy.value = false
  }
}

// Tasks --------------------------------------------------------------------

const openCreateTask = () => {
  editingTask.value = null
  taskFormError.value = ''
  taskFormOpen.value = true
}
const openEditTask = (task: AdminPlanTask) => {
  editingTask.value = task
  taskFormError.value = ''
  taskFormOpen.value = true
}
const onTaskSave = async (payload: AdminPlanTaskPayload) => {
  busy.value = true
  taskFormError.value = ''
  try {
    if (editingTask.value) {
      await updateAdminPlanTask(editingTask.value.id, payload)
    } else {
      await createAdminPlanTask(payload)
    }
    taskFormOpen.value = false
    editingTask.value = null
    await loadTasks()
  } catch (saveError) {
    logApiError('admin.plan.task-save', saveError)
    taskFormError.value = saveError instanceof Error ? saveError.message : 'Task could not be saved.'
  } finally {
    busy.value = false
  }
}
const openDeleteTask = (task: AdminPlanTask) => {
  taskPendingDelete.value = task
  deleteTaskError.value = ''
  deleteTaskConfirmOpen.value = true
}
const cancelDeleteTask = () => {
  taskPendingDelete.value = null
  deleteTaskError.value = ''
}
const confirmDeleteTask = async () => {
  const task = taskPendingDelete.value
  if (!task || busy.value) return
  busy.value = true
  deleteTaskError.value = ''
  try {
    await deleteAdminPlanTask(task.id)
    deleteTaskConfirmOpen.value = false
    taskPendingDelete.value = null
    clampPageAfterDelete()
    await loadTasks()
  } catch (deleteError) {
    logApiError('admin.plan.task-delete', deleteError)
    deleteTaskError.value =
      deleteError instanceof Error ? deleteError.message : 'Task could not be deleted.'
  } finally {
    busy.value = false
  }
}

onMounted(async () => {
  await loadStages()
  await loadTasks()
})
</script>

<style scoped>
.admin-plan__main {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.admin-plan__grid {
  display: grid;
  grid-template-columns: minmax(220px, 300px) 1fr;
  gap: 1.25rem;
  align-items: start;
}

.admin-plan__stages {
  border: 1px solid var(--border-light);
  border-radius: 10px;
  background-color: var(--white);
  padding: 1rem;
}

.admin-plan__panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.admin-plan__panel-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 700;
  color: var(--teal);
}

.admin-plan__stage-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.admin-plan__stage {
  display: flex;
  align-items: stretch;
  gap: 0.35rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  overflow: hidden;
}

.admin-plan__stage--active {
  border-color: var(--dark-green);
  box-shadow: inset 0 0 0 1px var(--dark-green);
}

.admin-plan__stage-select {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.15rem;
  padding: 0.55rem 0.7rem;
  border: 0;
  background: transparent;
  text-align: left;
  cursor: pointer;
  color: var(--teal);
  font: inherit;
}

.admin-plan__stage-name {
  font-weight: 600;
}

.admin-plan__stage-meta {
  font-size: 0.78rem;
  color: var(--text-muted);
}

.admin-plan__stage-actions {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.35rem;
}

.admin-plan__add {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.admin-plan__filter {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.admin-plan__filter-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.admin-plan__filter .app-select {
  min-width: 9rem;
  padding: 0.45rem 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  font-size: 0.9rem;
  font-family: inherit;
  background-color: var(--surface-elevated);
  color: var(--teal);
}

.admin-plan__error {
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

.admin-plan__dialog-error {
  margin: 0.9rem 0 0;
  padding: 0.65rem 0.75rem;
  border-left: 3px solid var(--danger);
  border-radius: 6px;
  background-color: rgba(220, 53, 69, 0.08);
  color: var(--danger);
  font-size: 0.9rem;
}

.admin-plan__primary {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.admin-plan__primary span {
  color: var(--text-muted);
}

.admin-plan__lock {
  margin-left: 0.4rem;
  color: var(--text-muted);
  font-size: 0.8rem;
}

.admin-plan__empty {
  color: var(--text-muted);
  font-size: 0.9rem;
  padding: 0.6rem 0.1rem;
}

.admin-plan__empty--panel {
  border: 1px dashed var(--border-light);
  border-radius: 10px;
  padding: 1.5rem;
  text-align: center;
  background-color: var(--white);
}

@media (max-width: 900px) {
  .admin-plan__grid {
    grid-template-columns: 1fr;
  }
}
</style>
