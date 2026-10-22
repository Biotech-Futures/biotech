<template>
  <div class="content-area plan-progress">
    <header class="page-header">
      <h1 class="page-title">Group Plan Progress</h1>
      <p class="page-subtitle">
        <template v-if="progress">{{ progress.year }} cohort · </template>
        Completed tasks across current group memberships.
      </p>
      <div class="plan-progress__actions">
        <RouterLink to="/admin/plan" class="btn btn-outline">Back to plan builder</RouterLink>
        <button class="btn btn-primary" type="button" :disabled="loading" @click="loadProgress">
          Refresh progress
        </button>
      </div>
    </header>

    <p v-if="loading" role="status">Loading plan progress…</p>
    <div v-if="error" class="plan-progress__error" role="alert">
      <p>{{ error }}</p>
      <button class="btn btn-outline" type="button" @click="loadProgress">Retry</button>
    </div>

    <template v-if="progress">
      <p class="plan-progress__legend">
        Each cell shows completed / total. Personal tasks count current members in that audience;
        whole-group tasks have one shared tick. 0/0 means there are no current members in that
        audience.
      </p>
      <p v-if="!progress.tasks.length" class="plan-progress__empty">
        No plan tasks yet. Add tasks in the plan builder to see progress.
      </p>
      <p v-else-if="!progress.groups.length" class="plan-progress__empty">
        No groups in the {{ progress.year }} cohort yet.
      </p>
      <AppDataTable
        v-else
        :columns="columns"
        :rows="rows"
        :search-columns="[groupColumn]"
        :sort="{ key: '', direction: 'asc' }"
        :selectable="false"
        :loading="loading"
        row-key="id"
        search-placeholder="Filter by group name"
        empty-message="No groups match this name."
      >
        <template #stats
          >{{ progress.groups.length }} groups · {{ progress.tasks.length }} tasks</template
        >
        <template v-for="task in progress.tasks" :key="task.id" #[`head-${taskKey(task.id)}`]>
          <span class="plan-progress__heading">
            <span class="plan-progress__stage">{{ stageName(task.stage_id) }}</span>
            <span>{{ task.name }}</span>
            <small
              >{{ audienceLabel(task.audience_role) }} ·
              {{ modeLabel(task.completion_mode) }}</small
            >
            <small v-if="task.due_date">Due {{ formatShortDate(task.due_date, 'UTC') }}</small>
          </span>
        </template>
        <template
          v-for="task in progress.tasks"
          :key="task.id"
          #[`cell-${taskKey(task.id)}`]="{ value }"
        >
          <span class="plan-progress__count">{{ value }}</span>
        </template>
      </AppDataTable>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import AppDataTable, { type DataTableColumn } from '@/components/AppDataTable.vue'
import {
  fetchAdminPlanProgress,
  type AdminPlanAudienceRole,
  type AdminPlanCompletionMode,
  type AdminPlanProgress,
} from '@/utils/adminAPI'
import { formatShortDate } from '@/utils/date'

const progress = ref<AdminPlanProgress | null>(null)
const loading = ref(false)
const error = ref('')
let requestId = 0

async function loadProgress() {
  const request = ++requestId
  loading.value = true
  error.value = ''
  try {
    const result = await fetchAdminPlanProgress()
    if (request === requestId) progress.value = result
  } catch (err) {
    if (request !== requestId) return
    progress.value = null
    error.value = err instanceof Error ? err.message : 'Plan progress could not be loaded.'
  } finally {
    if (request === requestId) loading.value = false
  }
}

const taskKey = (id: number) => `task_${id}`
const stageNames = computed(
  () => new Map(progress.value?.stages.map((stage) => [stage.id, stage.name])),
)
const stageName = (id: number) => stageNames.value.get(id) ?? 'Stage'
const audienceLabel = (role: AdminPlanAudienceRole) =>
  ({ student: 'Students', mentor: 'Mentors', supervisor: 'Supervisors' })[role]
const modeLabel = (mode: AdminPlanCompletionMode) =>
  mode === 'per_group' ? 'Whole group' : 'Each person'

const groupColumn: DataTableColumn = {
  key: 'name',
  label: 'Group',
  sortable: false,
  headClass: 'plan-progress__group-head',
  cellClass: () => 'plan-progress__group-cell',
  linkTo: (row) => `/groups/${row.id}`,
}
// The API supplies natural group order and stage/task order. Do not re-sort
// names lexically in AppDataTable (that would put BTF10 before BTF2).
const columns = computed<DataTableColumn[]>(() => [
  groupColumn,
  ...(progress.value?.tasks.map((task) => ({
    key: taskKey(task.id),
    label: `${stageName(task.stage_id)} · ${task.name}`,
    sortable: false,
    align: 'center' as const,
    title: `${stageName(task.stage_id)}: ${task.name}`,
  })) ?? []),
])
const rows = computed<Record<string, unknown>[]>(
  () =>
    progress.value?.groups.map((group) => ({
      id: group.id,
      name: group.name,
      ...Object.fromEntries(
        progress.value!.tasks.map((task) => {
          const cell = group.cells[String(task.id)]
          return [taskKey(task.id), `${cell.completed}/${cell.total}`]
        }),
      ),
    })) ?? [],
)

onMounted(loadProgress)
onBeforeUnmount(() => requestId++)
</script>

<style scoped>
.plan-progress__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 1rem;
}
.plan-progress__legend {
  color: var(--text-muted);
  margin: 1rem 0;
}
.plan-progress__heading {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-width: 10rem;
  max-width: 18rem;
  white-space: normal;
}
.plan-progress__stage,
.plan-progress__heading small {
  font-weight: 400;
  color: inherit;
}
.plan-progress__count {
  width: 100%;
  text-align: center;
  font-variant-numeric: tabular-nums;
}
:deep(.plan-progress__group-head),
:deep(.plan-progress__group-cell) {
  position: sticky;
  left: 0;
  z-index: 1;
  min-width: 6rem;
}
:deep(.plan-progress__group-head) {
  background: var(--dark-green);
  z-index: 2;
}
:deep(.plan-progress__group-cell) {
  background: var(--white);
}
.plan-progress__empty {
  padding: 1.5rem;
  background: var(--white);
  border: 1px solid var(--border-light);
  border-radius: 0.5rem;
}
.plan-progress__error {
  color: var(--danger);
  margin: 1rem 0;
}
</style>
