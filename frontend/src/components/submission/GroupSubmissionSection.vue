<template>
  <nav v-if="canSeeSubmission" class="group-sections" aria-label="Group sections">
    <button
      type="button"
      class="group-section-btn"
      :class="{ active: section === 'tasks' }"
      :aria-current="section === 'tasks' ? 'page' : undefined"
      data-testid="section-tab-tasks"
      @click="goToSection('tasks')"
    >
      Tasks and Chat
    </button>
    <button
      type="button"
      class="group-section-btn"
      :class="{ active: section === 'submission' }"
      :aria-current="section === 'submission' ? 'page' : undefined"
      data-testid="section-tab-submission"
      @click="goToSection('submission')"
    >
      Submission
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
</template>

<script setup lang="ts">
/** The group page's section switcher: Tasks and Chat (the slot) and Submission. */
import { computed, defineAsyncComponent, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// vue-router silently replaces a route that reuses this name, so keep it unique.
const SUBMISSION_ROUTE = 'group-submission'

const GroupSubmissionPage = defineAsyncComponent(
  () => import('@/views/GroupSubmissionPage.vue'),
)

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const canSeeSubmission = computed(() => auth.isStudent || auth.isMentor || auth.isSupervisor)

const groupId = computed(() => String(route.params.id ?? ''))

const section = computed(() =>
  route.name === SUBMISSION_ROUTE && canSeeSubmission.value ? 'submission' : 'tasks',
)

const hasOpenedSubmission = ref(false)
watch(
  section,
  (value) => {
    if (value === 'submission') hasOpenedSubmission.value = true
  },
  { immediate: true },
)

function goToSection(next: 'tasks' | 'submission') {
  const name = next === 'submission' ? SUBMISSION_ROUTE : 'group-detail'
  if (route.name === name) return
  router.push({ name, params: { id: groupId.value } })
}
</script>

<style scoped>
.group-sections {
  display: flex;
  gap: 1.25rem;
  margin-bottom: 1.25rem;
  border-bottom: 1px solid var(--border-light);
}

.group-section-btn {
  background: transparent;
  border: none;
  padding: 0.5rem 0.25rem;
  color: var(--charcoal);
  font-weight: 500;
  border-bottom: 3px solid transparent;
  cursor: pointer;
}

.group-section-btn.active {
  color: var(--dark-green);
  border-bottom-color: var(--dark-green);
}

/* Keeps the page's panes as direct flex children of .group-detail. */
.group-section-slot {
  display: contents;
}

.group-section-slot.is-hidden {
  display: none;
}

/* .group-detail hides overflow on desktop, so the form scrolls itself. */
.group-section-body {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
}
</style>
