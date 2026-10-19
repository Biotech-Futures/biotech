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

  <section
    v-if="section === 'results' && results"
    class="group-section-body"
    data-testid="section-body-results"
  >
    <GroupResults :group-id="groupId" :results="results" />
  </section>
</template>

<script setup lang="ts">
/** The group page's section switcher: Tasks and Chat (the slot), Submission,
 *  Finalist for a finalist team, and Results once marks or certificates are
 *  released. */
import { computed, defineAsyncComponent, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { fetchGroupResults, type GroupResults as GroupResultsData } from '@/utils/managementAPI'
import { fetchFinalist } from '@/utils/finalistAPI'

// vue-router silently replaces a route that reuses this name, so keep it unique.
const SUBMISSION_ROUTE = 'group-submission'
const FINALIST_ROUTE = 'group-finalist'
const RESULTS_ROUTE = 'group-results'

const GroupSubmissionPage = defineAsyncComponent(
  () => import('@/views/GroupSubmissionPage.vue'),
)
const GroupResults = defineAsyncComponent(() => import('./GroupResults.vue'))
const FinalistPage = defineAsyncComponent(() => import('@/views/FinalistPage.vue'))

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

const section = computed(() => {
  if (!canSeeSubmission.value) return 'tasks'
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

function goToSection(next: 'tasks' | 'submission' | 'finalist' | 'results') {
  const name = {
    tasks: 'group-detail',
    submission: SUBMISSION_ROUTE,
    finalist: FINALIST_ROUTE,
    results: RESULTS_ROUTE,
  }[next]
  if (route.name === name) return
  router.push({ name, params: { id: groupId.value } })
}
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
</style>
