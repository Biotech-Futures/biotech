<template>
  <div class="content-area plan-progress">
    <header class="page-header">
      <h1 class="page-title">Group Plan Progress</h1>
      <p class="page-subtitle">
        <template v-if="progress">{{ progress.year }} cohort · as of {{ todayLabel }} · </template>
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
      <p v-if="!progress.tasks.length" class="plan-progress__empty">
        No plan tasks yet. Add tasks in the plan builder to see progress.
      </p>
      <p v-else-if="!progress.groups.length" class="plan-progress__empty">
        No groups in the {{ progress.year }} cohort yet.
      </p>
      <template v-else>
        <!-- Cohort health first: how many groups need attention. -->
        <section class="plan-progress__health" aria-label="Cohort health">
          <p class="plan-progress__headline">
            {{ behindCount }} of {{ groupSummaries.length }} groups have overdue tasks
          </p>
          <div class="plan-progress__split" aria-hidden="true">
            <span class="plan-progress__split-ok" :style="{ width: `${onTrackPercent}%` }"></span>
            <span class="plan-progress__split-behind" :style="{ width: `${100 - onTrackPercent}%` }"></span>
          </div>
          <ul class="plan-progress__key">
            <li>
              <span class="plan-progress__dot plan-progress__dot--ok"></span>
              {{ groupSummaries.length - behindCount }} on track
            </li>
            <li>
              <span class="plan-progress__dot plan-progress__dot--behind"></span>
              {{ behindCount }} behind · {{ overdueTotal }} overdue
              {{ overdueTotal === 1 ? 'task' : 'tasks' }} in total
            </li>
            <li>{{ cohortPercent }}% of all applicable tasks done</li>
          </ul>
        </section>

        <div class="plan-progress__tabs" role="group" aria-label="View">
          <button
            type="button"
            class="plan-progress__tab"
            :class="{ 'plan-progress__tab--active': view === 'group' }"
            :aria-pressed="view === 'group'"
            @click="view = 'group'"
          >
            By group
          </button>
          <button
            type="button"
            class="plan-progress__tab"
            :class="{ 'plan-progress__tab--active': view === 'task' }"
            :aria-pressed="view === 'task'"
            @click="view = 'task'"
          >
            By task
          </button>
        </div>

        <!-- By group: one row per group, behind first; open a row for its tasks. -->
        <AppDataTable
          v-if="view === 'group'"
          key="groups"
          :columns="groupColumns"
          :rows="groupRows"
          :search-columns="[groupNameColumn]"
          :sort="{ key: '', direction: 'asc' }"
          :selectable="false"
          :loading="loading"
          row-key="id"
          search-placeholder="Filter by group name"
          empty-message="No groups match."
        >
          <template #filters>
            <div class="plan-progress__segments" role="group" aria-label="Show">
              <button
                v-for="option in filterOptions"
                :key="option.id"
                type="button"
                class="plan-progress__segment"
                :class="{ 'plan-progress__segment--active': filter === option.id }"
                :aria-pressed="filter === option.id"
                @click="filter = option.id"
              >
                {{ option.label }}
              </button>
            </div>
          </template>
          <template #stats>Groups needing attention are listed first</template>
          <template #cell-status="{ row }">
            <span class="plan-progress__status" :class="`plan-progress__status--${toGroup(row).tone}`">
              <span class="plan-progress__dot" :class="`plan-progress__dot--${toGroup(row).tone}`"></span>
              {{ toGroup(row).status }}
            </span>
          </template>
          <template #cell-progress="{ row }">
            <span class="plan-progress__progress">
              <span class="plan-progress__bar" aria-hidden="true">
                <span :style="{ width: `${toGroup(row).percent}%` }"></span>
              </span>
              <span class="plan-progress__count">
                {{ toGroup(row).done }} of {{ toGroup(row).applicable }} tasks
              </span>
            </span>
          </template>
          <template #cell-hint="{ row }">
            <span class="plan-progress__muted">{{ toGroup(row).hint }}</span>
          </template>
          <template #row-detail="{ row }">
            <div class="plan-progress__detail">
              <div v-for="stage in detailStages(toGroup(row))" :key="stage.id" class="plan-progress__detail-stage">
                <p class="plan-progress__detail-title">{{ stage.name }}</p>
                <ul>
                  <li v-for="item in stage.items" :key="item.id" :class="`plan-progress__item--${item.state}`">
                    <i :class="stateIcon[item.state]" :aria-label="stateLabel[item.state]" role="img"></i>
                    <span class="plan-progress__item-name">{{ item.name }}</span>
                    <span class="plan-progress__item-meta">{{ item.meta }}</span>
                  </li>
                </ul>
              </div>
            </div>
          </template>
        </AppDataTable>

        <!-- By task: each task once, with how many groups have done it. -->
        <AppDataTable
          v-else
          key="tasks"
          :columns="taskColumns"
          :rows="taskRows"
          :search-columns="[taskNameColumn]"
          :sort="{ key: '', direction: 'asc' }"
          :selectable="false"
          :loading="loading"
          two-line-rows
          row-key="id"
          search-placeholder="Filter by task name"
          empty-message="No tasks match."
        >
          <template #stats>{{ progress.tasks.length }} tasks</template>
          <template #cell-name="{ row }">
            <span class="plan-progress__task">
              <strong>{{ row.name }}</strong>
              <span class="plan-progress__muted">
                <i class="fas" :class="row.shared ? 'fa-users' : 'fa-user'" aria-hidden="true"></i>
                {{ row.who }}
              </span>
            </span>
          </template>
          <template #cell-done="{ row }">
            <span class="plan-progress__progress">
              <span class="plan-progress__bar" aria-hidden="true">
                <span :style="{ width: `${row.percent}%` }"></span>
              </span>
              <span class="plan-progress__count">{{ row.done }} of {{ row.applicable }} groups</span>
            </span>
          </template>
          <template #cell-overdue="{ row }">
            <span :class="row.overdue ? 'plan-progress__late' : 'plan-progress__muted'">
              {{ row.overdueText }}
            </span>
          </template>
        </AppDataTable>
      </template>
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
import { formatShortDate, getSetTimeZone, toTimeZoneDateKey } from '@/utils/date'

type Task = AdminPlanProgress['tasks'][number]
type Group = AdminPlanProgress['groups'][number]
type CellState = 'done' | 'overdue' | 'open' | 'na'
type GroupSummary = {
  id: number
  name: string
  group: Group
  done: number
  applicable: number
  overdue: Task[]
  percent: number
  status: string
  tone: 'behind' | 'ok' | 'idle'
  hint: string
}

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

const view = ref<'group' | 'task'>('group')
const filter = ref<'all' | 'behind' | 'ok'>('all')

// Due dates are date-only: shown in UTC (no day shift) and compared with
// today in the viewer's set time zone. Due today isn't overdue.
const today = toTimeZoneDateKey(new Date(), getSetTimeZone())
const todayLabel = formatShortDate(today, 'UTC')
const dueLabel = (task: Task) => formatShortDate(task.due_date, 'UTC')

const audienceLabel = (role: AdminPlanAudienceRole) =>
  ({ student: 'Students', mentor: 'Mentors', supervisor: 'Supervisors' })[role]
const modeLabel = (mode: AdminPlanCompletionMode) =>
  mode === 'per_group' ? 'one tick per group' : 'each person'

// A cell with nobody in the task's audience (0/0) has nothing to do and is
// left out of every total.
function cellState(task: Task, group: Group): CellState {
  const { completed, total } = group.cells[String(task.id)]
  if (total === 0) return 'na'
  if (completed >= total) return 'done'
  return task.due_date && task.due_date < today ? 'overdue' : 'open'
}

const byDue = (a: Task, b: Task) => (a.due_date ?? '9999').localeCompare(b.due_date ?? '9999')

// A group is behind when it has at least one overdue task.
const groupSummaries = computed<GroupSummary[]>(() =>
  (progress.value?.groups ?? []).map((group) => {
    const tasks = progress.value!.tasks
    const states = tasks.map((task) => cellState(task, group))
    const applicable = states.filter((state) => state !== 'na').length
    const done = states.filter((state) => state === 'done').length
    const overdue = tasks.filter((_, index) => states[index] === 'overdue').sort(byDue)
    const next = tasks.filter((_, index) => states[index] === 'open').sort(byDue)[0]
    let status = 'On track'
    let tone: GroupSummary['tone'] = 'ok'
    let hint = next
      ? `Next: ${next.name}${next.due_date ? ` · due ${dueLabel(next)}` : ''}`
      : 'All tasks done'
    if (overdue.length) {
      status = `${overdue.length} overdue`
      tone = 'behind'
      hint = `Oldest overdue: ${overdue[0].name} (due ${dueLabel(overdue[0])})`
    } else if (!applicable) {
      status = 'Nothing to tick'
      tone = 'idle'
      hint = 'No current members in these tasks’ audiences'
    } else if (done === applicable) {
      status = 'All done'
    }
    return {
      id: group.id,
      name: group.name,
      group,
      done,
      applicable,
      overdue,
      percent: applicable ? Math.round((done / applicable) * 100) : 0,
      status,
      tone,
      hint,
    }
  }),
)

const behindCount = computed(() => groupSummaries.value.filter((g) => g.overdue.length).length)
const overdueTotal = computed(() =>
  groupSummaries.value.reduce((sum, g) => sum + g.overdue.length, 0),
)
const onTrackPercent = computed(() =>
  groupSummaries.value.length
    ? Math.round(((groupSummaries.value.length - behindCount.value) / groupSummaries.value.length) * 100)
    : 0,
)
const cohortPercent = computed(() => {
  const applicable = groupSummaries.value.reduce((sum, g) => sum + g.applicable, 0)
  const done = groupSummaries.value.reduce((sum, g) => sum + g.done, 0)
  return applicable ? Math.round((done / applicable) * 100) : 0
})

const filterOptions = computed(() => [
  { id: 'all' as const, label: `All ${groupSummaries.value.length}` },
  { id: 'behind' as const, label: `Behind ${behindCount.value}` },
  { id: 'ok' as const, label: `On track ${groupSummaries.value.length - behindCount.value}` },
])

const groupNameColumn: DataTableColumn = {
  key: 'name',
  label: 'Group',
  sortable: false,
  primary: true,
  linkTo: (row) => `/groups/${row.id}`,
}
const groupColumns: DataTableColumn[] = [
  groupNameColumn,
  { key: 'status', label: 'Status', sortable: false },
  { key: 'progress', label: 'Progress', sortable: false },
  { key: 'hint', label: 'Needs doing', sortable: false, wrap: true },
]
// Behind groups first, most overdue first; otherwise the API's natural group
// order (BTF2 before BTF10), which the table must not re-sort lexically.
const groupRows = computed<Record<string, unknown>[]>(() =>
  groupSummaries.value
    .map((summary, index) => ({ summary, index }))
    .filter(({ summary }) =>
      filter.value === 'all' ? true : filter.value === 'behind' ? summary.overdue.length > 0 : !summary.overdue.length,
    )
    .sort((a, b) => b.summary.overdue.length - a.summary.overdue.length || a.index - b.index)
    .map(({ summary }) => ({ ...summary })),
)
const toGroup = (row: Record<string, unknown>) => row as unknown as GroupSummary

const stateIcon: Record<CellState, string> = {
  done: 'fas fa-check',
  overdue: 'fas fa-clock',
  open: 'far fa-circle',
  na: 'fas fa-minus',
}
const stateLabel: Record<CellState, string> = {
  done: 'Done',
  overdue: 'Overdue',
  open: 'Not done yet',
  na: 'Nobody to tick',
}
function detailStages(summary: GroupSummary) {
  const data = progress.value
  if (!data) return []
  return data.stages
    .map((stage) => ({
      id: stage.id,
      name: stage.name,
      items: data.tasks
        .filter((task) => task.stage_id === stage.id)
        .map((task) => {
          const state = cellState(task, summary.group)
          const { completed, total } = summary.group.cells[String(task.id)]
          let meta = `${completed}/${total}`
          if (state === 'na') meta = 'nobody to tick'
          else if (task.completion_mode === 'per_group') meta = state === 'done' ? 'done' : 'not done'
          if (state === 'overdue') meta += ` · was due ${dueLabel(task)}`
          return { id: task.id, name: task.name, state, meta }
        }),
    }))
    .filter((stage) => stage.items.length)
}

const taskNameColumn: DataTableColumn = { key: 'name', label: 'Task', sortable: false }
const taskColumns: DataTableColumn[] = [
  taskNameColumn,
  { key: 'stage', label: 'Stage', sortable: false },
  { key: 'due', label: 'Due', sortable: false },
  { key: 'done', label: 'Groups done', sortable: false },
  { key: 'overdue', label: 'Overdue', sortable: false },
]
// In the API's stage/task order.
const taskRows = computed<Record<string, unknown>[]>(() => {
  const data = progress.value
  if (!data) return []
  const stageNames = new Map(data.stages.map((stage) => [stage.id, stage.name]))
  return data.tasks.map((task) => {
    let done = 0
    let applicable = 0
    let overdue = 0
    for (const group of data.groups) {
      const state = cellState(task, group)
      if (state === 'na') continue
      applicable++
      if (state === 'done') done++
      if (state === 'overdue') overdue++
    }
    return {
      id: task.id,
      name: task.name,
      shared: task.completion_mode === 'per_group',
      who: `${audienceLabel(task.audience_role)} · ${modeLabel(task.completion_mode)}`,
      stage: stageNames.get(task.stage_id) ?? 'Stage',
      due: task.due_date ? dueLabel(task) : 'No due date',
      done,
      applicable,
      percent: applicable ? Math.round((done / applicable) * 100) : 0,
      overdue,
      overdueText: overdue
        ? `${overdue} ${overdue === 1 ? 'group' : 'groups'} overdue`
        : task.due_date && task.due_date < today
          ? 'None'
          : 'Not due yet',
    }
  })
})

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
.plan-progress__health {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin: 1rem 0;
  padding: 1.25rem 1.5rem;
  background: var(--white);
  border: 1px solid var(--border-light);
  border-radius: 10px;
}
.plan-progress__headline {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
}
.plan-progress__split {
  display: flex;
  height: 10px;
  border-radius: 999px;
  overflow: hidden;
  background: var(--border-light);
}
.plan-progress__split-ok {
  background: var(--dark-green);
}
.plan-progress__split-behind {
  background: var(--danger);
}
.plan-progress__key {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 1.5rem;
  margin: 0;
  padding: 0;
  list-style: none;
  font-size: 0.875rem;
  color: var(--text-muted);
}
.plan-progress__key li {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}
.plan-progress__dot {
  display: inline-block;
  width: 0.6rem;
  height: 0.6rem;
  border-radius: 50%;
  flex: 0 0 auto;
}
.plan-progress__dot--ok {
  background: var(--dark-green);
}
.plan-progress__dot--behind {
  background: var(--danger);
}
.plan-progress__dot--idle {
  background: var(--border-light);
}
.plan-progress__tabs {
  display: flex;
  gap: 0.25rem;
  margin-bottom: 1rem;
  border-bottom: 1px solid var(--border-light);
}
.plan-progress__tab {
  min-height: 44px;
  padding: 0 1rem;
  margin-bottom: -1px;
  border: 0;
  border-bottom: 3px solid transparent;
  background: transparent;
  color: var(--text-muted);
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}
.plan-progress__tab--active {
  color: var(--dark-green);
  border-bottom-color: var(--dark-green);
}
.plan-progress__segments {
  display: flex;
  padding: 3px;
  background: var(--white);
  border: 1px solid var(--border-light);
  border-radius: 8px;
}
.plan-progress__segment {
  padding: 0.35rem 0.85rem;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--teal);
  font: inherit;
  font-size: 0.875rem;
  cursor: pointer;
}
.plan-progress__segment--active {
  background: var(--teal);
  color: var(--white);
  font-weight: 600;
}
.plan-progress__status {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
}
.plan-progress__status--behind {
  color: var(--danger);
  font-weight: 600;
}
.plan-progress__status--ok {
  color: var(--dark-green);
}
.plan-progress__status--idle,
.plan-progress__muted {
  color: var(--text-muted);
}
.plan-progress__progress {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  min-width: 12rem;
}
.plan-progress__bar {
  flex: 1;
  height: 6px;
  border-radius: 999px;
  background: var(--border-light);
  overflow: hidden;
}
.plan-progress__bar span {
  display: block;
  height: 100%;
  background: var(--dark-green);
}
.plan-progress__count {
  flex: 0 0 auto;
  font-size: 0.875rem;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}
.plan-progress__detail {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(15rem, 1fr));
  gap: 1rem 2rem;
  padding: 0.5rem 0.5rem 0.75rem;
}
.plan-progress__detail-title {
  margin: 0 0 0.35rem;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-muted);
}
.plan-progress__detail ul {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin: 0;
  padding: 0;
  list-style: none;
}
.plan-progress__detail li {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  font-size: 0.875rem;
}
.plan-progress__detail li i {
  width: 1rem;
  text-align: center;
  color: var(--text-muted);
}
.plan-progress__item--done i {
  color: var(--dark-green);
}
.plan-progress__item--overdue i,
.plan-progress__item--overdue .plan-progress__item-meta {
  color: var(--danger);
}
.plan-progress__item--na .plan-progress__item-name {
  color: var(--text-muted);
}
.plan-progress__item-name {
  flex: 1;
}
.plan-progress__item-meta {
  font-size: 0.8rem;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}
.plan-progress__task {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}
.plan-progress__task .plan-progress__muted {
  font-size: 0.8rem;
}
.plan-progress__late {
  color: var(--danger);
  font-weight: 600;
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
