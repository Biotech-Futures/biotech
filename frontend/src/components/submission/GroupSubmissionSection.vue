<template>
  <nav v-if="canSeeSubmission" class="group-sections tab-bar" aria-label="Group sections">
    <button
      type="button"
      class="tab-pill"
      :class="{ active: section === 'tasks' }"
      :aria-current="section === 'tasks' ? 'page' : undefined"
      data-testid="section-tab-tasks"
      @click="goToSection('tasks')"
    >
      Tasks and Chat
    </button>
    <!-- Only when the group's plan has tasks this viewer can see. -->
    <button
      v-if="hasPlan"
      type="button"
      class="tab-pill"
      :class="{ active: section === 'plan' }"
      :aria-current="section === 'plan' ? 'page' : undefined"
      data-testid="section-tab-plan"
      @click="goToSection('plan')"
    >
      Plan
    </button>
    <!-- A plan that failed to load (not one that's empty or not ours to see)
         is offered again rather than silently dropped. -->
    <button
      v-if="planStatus === 'error'"
      type="button"
      class="tab-pill"
      data-testid="section-plan-retry"
      @click="loadPlan()"
    >
      Plan didn't load · Retry
    </button>
    <button
      type="button"
      class="tab-pill"
      :class="{ active: section === 'submission' }"
      :aria-current="section === 'submission' ? 'page' : undefined"
      data-testid="section-tab-submission"
      @click="goToSection('submission')"
    >
      Submission
    </button>
    <!-- Only for a finalist team, once it's been told. -->
    <button
      v-if="isFinalist"
      type="button"
      class="tab-pill"
      :class="{ active: section === 'finalist' }"
      :aria-current="section === 'finalist' ? 'page' : undefined"
      data-testid="section-tab-finalist"
      @click="goToSection('finalist')"
    >
      Finalist
    </button>
    <!-- Only once marks or certificates are released. -->
    <button
      v-if="resultsReleased"
      type="button"
      class="tab-pill"
      :class="{ active: section === 'results' }"
      :aria-current="section === 'results' ? 'page' : undefined"
      data-testid="section-tab-results"
      @click="goToSection('results')"
    >
      Results
    </button>
  </nav>

  <!-- Hidden rather than destroyed, so live task and chat state survives tab changes. -->
  <div
    class="group-section-slot"
    :class="{ 'is-hidden': section !== 'tasks' }"
    data-testid="section-body-tasks"
  >
    <slot />
  </div>

  <!-- Mounted on first open, then hidden rather than destroyed. -->
  <section
    v-show="section === 'submission'"
    class="group-section-body"
    data-testid="section-body-submission"
  >
    <GroupSubmissionPage v-if="hasOpenedSubmission" />
  </section>

  <!-- The finalist round: its own availability, presentation and submit. -->
  <section
    v-show="section === 'finalist'"
    class="group-section-body"
    data-testid="section-body-finalist"
  >
    <FinalistPage v-if="hasOpenedFinalist" />
  </section>

  <!-- Keyed by group, so one group's ticks never show for another. -->
  <section v-if="section === 'plan'" class="group-section-body" data-testid="section-body-plan">
    <p v-if="planStatus === 'loading'" class="group-plan-state" role="status">Loading the plan…</p>
    <p v-else-if="planStatus === 'error'" class="group-plan-state" role="alert">
      The plan couldn't be loaded.
      <button type="button" class="btn btn-outline btn-sm" @click="loadPlan()">Retry</button>
    </p>
    <GroupPlanSection
      v-else-if="plan"
      :key="groupId"
      :group-id="groupId"
      :stages="plan.stages"
      :items="plan.items"
      @task-updated="onPlanTaskUpdated"
    />
  </section>

  <section
    v-if="section === 'results' && results"
    class="group-section-body"
    data-testid="section-body-results"
  >
    <GroupResults :group-id="groupId" :results="results" />
  </section>
</template>

<script setup lang="ts">
/** The group page's section switcher: Tasks and Chat (the slot), Plan when
 *  the group's plan has tasks for this viewer, Submission, Finalist for a
 *  finalist team, and Results once marks or certificates are released. */
import { computed, defineAsyncComponent, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { fetchGroupResults, type GroupResults as GroupResultsData } from '@/utils/managementAPI'
import { fetchFinalist } from '@/utils/finalistAPI'
import { listGroupPlanTasks, type GroupPlanList, type GroupPlanTask } from '@/utils/plansAPI'
import { ApiError } from '@/utils/apiError'

// vue-router silently replaces a route that reuses this name, so keep it unique.
const SUBMISSION_ROUTE = 'group-submission'
const FINALIST_ROUTE = 'group-finalist'
const RESULTS_ROUTE = 'group-results'
const PLAN_ROUTE = 'group-plan'

const GroupSubmissionPage = defineAsyncComponent(
  () => import('@/views/GroupSubmissionPage.vue'),
)
const GroupResults = defineAsyncComponent(() => import('./GroupResults.vue'))
const FinalistPage = defineAsyncComponent(() => import('@/views/FinalistPage.vue'))
const GroupPlanSection = defineAsyncComponent(
  () => import('@/components/plans/GroupPlanSection.vue'),
)

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

// Admins too: they can edit, submit and reopen for a team that needs a hand.
const canSeeSubmission = computed(
  () => auth.isStudent || auth.isMentor || auth.isSupervisor || auth.isAdmin
)

const groupId = computed(() => String(route.params.id ?? ''))

// What's out for this group; the Results tab shows once marks or
// certificates are released.
const results = ref<GroupResultsData | null>(null)
const resultsReleased = computed(() =>
  Boolean(results.value?.marks_released || results.value?.certificates_released),
)

watch(
  groupId,
  async (id) => {
    results.value = null
    if (!id || !canSeeSubmission.value) return
    try {
      const loaded = await fetchGroupResults(id)
      if (id === groupId.value) results.value = loaded
    } catch {
      // No Results tab when they can't be read.
    }
  },
  { immediate: true },
)

// Asked of the server, which alone knows whether this group is a finalist
// (flagged and told).
const isFinalist = ref(false)

watch(
  groupId,
  async (id) => {
    isFinalist.value = false
    if (!id || !canSeeSubmission.value) return
    try {
      await fetchFinalist(id)
      if (id === groupId.value) isFinalist.value = true
    } catch {
      // Not a finalist: no Finalist tab.
    }
  },
  { immediate: true },
)

// The group's plan, as the server shows it to this viewer. "unavailable" is
// an empty plan or one the viewer can't see (404/403): no Plan tab and no
// error. "error" is anything else, offered again with a retry.
type PlanStatus = 'idle' | 'loading' | 'ready' | 'unavailable' | 'error'
const plan = ref<GroupPlanList | null>(null)
const planStatus = ref<PlanStatus>('idle')
const hasPlan = computed(() => planStatus.value === 'ready' && Boolean(plan.value?.items.length))

// Each load is numbered so only the newest answer lands: a late reply for
// the previous group, or for a load a retry has overtaken, is dropped.
let planRequest = 0

async function loadPlan({ quiet = false } = {}) {
  const id = groupId.value
  const request = ++planRequest
  if (!id || !canSeeSubmission.value) {
    plan.value = null
    planStatus.value = 'idle'
    return
  }
  // A quiet reload keeps the current plan on screen until the answer.
  if (!quiet) planStatus.value = 'loading'
  try {
    const loaded = await listGroupPlanTasks(id)
    if (request !== planRequest) return
    plan.value = loaded.items.length ? loaded : null
    planStatus.value = loaded.items.length ? 'ready' : 'unavailable'
  } catch (err) {
    if (request !== planRequest) return
    const status = err instanceof ApiError ? err.status : undefined
    const hidden = status === 404 || status === 403
    // A quiet reload that fails for a passing reason keeps the plan already
    // on screen, ticks and all; the next visit to Plan tries again.
    if (quiet && plan.value && !hidden) return
    plan.value = null
    planStatus.value = hidden ? 'unavailable' : 'error'
  }
}

// A tick the server saved, taken into this copy of the plan so coming back
// to Plan shows it. A load still in flight is dropped: it may have read the
// plan before the tick landed and would put the old value back. A tick for a
// group no longer shown is ignored, as task ids are shared across groups.
function onPlanTaskUpdated(id: string, updated: GroupPlanTask) {
  if (id !== groupId.value || !plan.value || planStatus.value !== 'ready') return
  planRequest++
  plan.value = {
    ...plan.value,
    items: plan.value.items.map((item) => (item.id === updated.id ? updated : item)),
  }
}

// Cleared at once, so another group's Plan tab or tasks never show.
watch(
  groupId,
  () => {
    plan.value = null
    planStatus.value = 'idle'
    void loadPlan()
  },
  { immediate: true },
)

const section = computed(() => {
  if (!canSeeSubmission.value) return 'tasks'
  // Open while the plan loads or can be retried, so a Plan link doesn't
  // flash Tasks and Chat first; never for an empty or hidden plan.
  if (route.name === PLAN_ROUTE && (hasPlan.value || ['idle', 'loading', 'error'].includes(planStatus.value))) {
    return 'plan'
  }
  if (route.name === SUBMISSION_ROUTE) return 'submission'
  if (route.name === FINALIST_ROUTE && isFinalist.value) return 'finalist'
  if (route.name === RESULTS_ROUTE && resultsReleased.value) return 'results'
  return 'tasks'
})

const hasOpenedSubmission = ref(false)
const hasOpenedFinalist = ref(false)
watch(
  section,
  (value) => {
    if (value === 'submission') hasOpenedSubmission.value = true
    if (value === 'finalist') hasOpenedFinalist.value = true
  },
  { immediate: true },
)

function goToSection(next: 'tasks' | 'plan' | 'submission' | 'finalist' | 'results') {
  const name = {
    tasks: 'group-detail',
    plan: PLAN_ROUTE,
    submission: SUBMISSION_ROUTE,
    finalist: FINALIST_ROUTE,
    results: RESULTS_ROUTE,
  }[next]
  if (route.name === name) return
  router.push({ name, params: { id: groupId.value } })
}

// Coming back to Plan from another section reloads it, so an admin's edits
// show. Landing on the Plan URL needs no second load: the group watch made one.
watch(
  () => route.name,
  (name, previous) => {
    if (name === PLAN_ROUTE && previous !== PLAN_ROUTE && planStatus.value === 'ready') {
      void loadPlan({ quiet: true })
    }
  },
)

// No plan to show here (empty, or not the viewer's to see): leave the Plan
// URL for the group page rather than sit on a section that can't open.
watch(
  [planStatus, () => route.name],
  ([status, name]) => {
    if (name === PLAN_ROUTE && status === 'unavailable') {
      void router.replace({ name: 'group-detail', params: { id: groupId.value } })
    }
  },
)
</script>

<style scoped>
/* The shared tab bar, start-aligned in the group page's column. */
.group-sections {
  align-self: flex-start;
}

/* Keeps the page's panes as direct flex children of .group-detail. */
.group-section-slot {
  display: contents;
}

.group-section-slot.is-hidden {
  display: none;
}

/* The page takes the section's height while one is open, so it scrolls
   with the page rather than within itself. */
.group-section-body {
  flex: 1 1 auto;
}

.group-plan-state {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin: 0;
  color: var(--text-muted);
}
</style>
