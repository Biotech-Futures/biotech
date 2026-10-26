<template>
  <!-- The group's plan: stages in order, each with its tasks. The parent loads
       the plan and keys this component by group, so it never shows another
       group's ticks. What can be ticked is the server's call (can_toggle). -->
  <div class="group-plan">
    <p v-if="!planStages.length" class="group-plan__muted">There are no plan tasks yet.</p>

    <section
      v-for="stage in planStages"
      :key="stage.id"
      class="card group-plan__stage"
      :data-testid="`plan-stage-${stage.id}`"
    >
      <header class="group-plan__stage-head">
        <h2 class="card-title">{{ stage.name }}</h2>
        <!-- Counts only tasks with a tick of the viewer's own or the group's;
             someone else's individual task (completed null) is left out. -->
        <p v-if="stage.total" class="group-plan__summary" data-testid="plan-stage-summary">
          Your view: {{ stage.done }}/{{ stage.total }} tasks complete
        </p>
      </header>
      <p v-if="stage.description" class="group-plan__text group-plan__muted">{{ stage.description }}</p>

      <ul class="group-plan__tasks">
        <li
          v-for="task in stage.tasks"
          :key="task.id"
          class="group-plan__task"
          :data-testid="`plan-task-${task.id}`"
        >
          <div class="group-plan__task-head">
            <!-- No box for someone else's individual task: it isn't the
                 viewer's to tick, and an empty box would suggest it was. -->
            <span v-if="task.completed === null" class="group-plan__muted group-plan__each">
              Each person ticks their own
            </span>
            <input
              v-else
              :id="`plan-task-check-${task.id}`"
              type="checkbox"
              class="group-plan__check"
              :checked="task.completed"
              :disabled="!task.can_toggle || saving.has(task.id)"
              :aria-busy="saving.has(task.id) || undefined"
              @change="onToggle(task, $event)"
            />
            <label
              :for="task.completed === null ? undefined : `plan-task-check-${task.id}`"
              class="group-plan__name"
            >
              {{ task.name }}
            </label>
            <span v-if="task.completion_mode === 'per_group'" class="group-plan__tag">Whole group</span>
            <span v-if="isOverdue(task)" class="group-plan__tag group-plan__tag--overdue">Overdue</span>
          </div>

          <!-- Plain text: instructions are never rendered as HTML. -->
          <p v-if="task.description" class="group-plan__text">{{ task.description }}</p>

          <p v-if="task.due_date || resourceHref(task)" class="group-plan__meta">
            <span v-if="task.due_date">Due {{ formatShortDate(task.due_date, 'UTC') }}</span>
            <a
              v-if="resourceHref(task)"
              :href="resourceHref(task)!"
              target="_blank"
              rel="noopener noreferrer"
              class="group-plan__link"
            >
              {{ task.resource_label.trim() || 'Open resource' }}
            </a>
          </p>

          <p v-if="errors[task.id]" class="group-plan__error" role="alert">{{ errors[task.id] }}</p>
        </li>
      </ul>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { formatShortDate, getSetTimeZone, toTimeZoneDateKey } from '@/utils/date'
import { toggleGroupPlanTask, type GroupPlanTask, type PlanStage } from '@/utils/plansAPI'

const props = defineProps<{ groupId: string; stages: PlanStage[]; items: GroupPlanTask[] }>()
// A saved tick, with the group it was saved for, so the parent's copy of the
// plan keeps it. Only after the server agrees; never for a failed tick.
const emit = defineEmits<{ taskUpdated: [groupId: string, task: GroupPlanTask] }>()

// The shown tasks. A tick replaces its task with the server's answer; a new
// list from the parent (e.g. a reload, or the parent taking in a tick)
// replaces them all.
const tasks = ref<GroupPlanTask[]>([...props.items])
watch(
  () => props.items,
  (items) => {
    tasks.value = [...items]
  },
)

// Stages in plan order with their tasks (in the server's order) and the
// viewer's summary; a stage without visible tasks is left out.
const planStages = computed(() =>
  props.stages
    .map((stage) => {
      const stageTasks = tasks.value.filter((task) => task.stage_id === stage.id)
      const counted = stageTasks.filter((task) => task.completed !== null)
      return {
        ...stage,
        tasks: stageTasks,
        done: counted.filter((task) => task.completed === true).length,
        total: counted.length,
      }
    })
    .filter((stage) => stage.tasks.length > 0),
)

// Due dates are date-only, so they are formatted in UTC (no day shift) and
// compared with today in the viewer's set time zone. Due today isn't overdue,
// and neither is anything done or not the viewer's to tick (null).
const isOverdue = (task: GroupPlanTask) =>
  task.completed === false &&
  Boolean(task.due_date) &&
  task.due_date! < toTimeZoneDateKey(new Date(), getSetTimeZone())

// Only web links: a resource is never a script, mail or relative link.
const resourceHref = (task: GroupPlanTask) => {
  const url = task.resource_url.trim()
  return /^https?:\/\/\S+$/i.test(url) ? url : null
}

const saving = ref(new Set<number>())
const errors = ref<Record<number, string>>({})

async function onToggle(task: GroupPlanTask, event: Event) {
  const box = event.target as HTMLInputElement
  // The box shows the saved state until the server agrees, so put it back.
  box.checked = task.completed === true
  if (saving.value.has(task.id) || !task.can_toggle) return

  saving.value = new Set(saving.value).add(task.id)
  const cleared = { ...errors.value }
  delete cleared[task.id]
  errors.value = cleared
  try {
    const updated = await toggleGroupPlanTask(props.groupId, task.id, task.completed !== true)
    tasks.value = tasks.value.map((item) => (item.id === updated.id ? updated : item))
    emit('taskUpdated', props.groupId, updated)
  } catch (err) {
    errors.value = {
      ...errors.value,
      [task.id]: `${apiErrorFromUnknown(err).message} Your tick wasn't saved; please try again.`,
    }
  } finally {
    const next = new Set(saving.value)
    next.delete(task.id)
    saving.value = next
  }
}
</script>

<style scoped>
.group-plan {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.group-plan__stage {
  height: auto;
  min-height: 0;
  padding: 1.25rem 1.5rem;
  overflow: visible;
  /* The section's gap spaces the cards, not .card's own margin. */
  margin-bottom: 0;
}

.group-plan__stage-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.group-plan__summary {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.875rem;
}

.group-plan__muted {
  color: var(--text-muted);
}

/* Keep the line breaks typed into stage and task text. */
.group-plan__text {
  margin: 0.25rem 0 0;
  white-space: pre-line;
}

.group-plan__tasks {
  list-style: none;
  margin: 1rem 0 0;
  padding: 0;
}

.group-plan__task {
  padding: 0.75rem 0;
  border-top: 1px solid var(--border-light);
}

.group-plan__task-head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.group-plan__check {
  width: 1.1rem;
  height: 1.1rem;
  margin: 0;
}

.group-plan__name {
  font-weight: 600;
}

.group-plan__each {
  font-size: 0.8rem;
}

.group-plan__tag {
  padding: 0.1rem 0.5rem;
  border-radius: 999px;
  background-color: var(--light-green);
  color: var(--dark-green);
  font-size: 0.7rem;
  font-weight: 600;
}

.group-plan__tag--overdue {
  background-color: var(--danger);
  color: var(--white);
}

.group-plan__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  margin: 0.35rem 0 0;
  color: var(--text-muted);
  font-size: 0.85rem;
}

.group-plan__link {
  color: var(--teal);
  text-decoration: underline;
}

.group-plan__error {
  margin: 0.35rem 0 0;
  color: var(--danger);
  font-size: 0.85rem;
}
</style>
