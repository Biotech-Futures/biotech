<template>
  <!-- Only when there is a choice: the server refuses mentors and supervisors, so
       a tab would lead somewhere they cannot go. -->
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

  <!-- Hidden, not destroyed: the group page keeps live task and chat state that a
       v-if would tear down on every tab change. -->
  <div
    class="group-section-slot"
    :class="{ 'is-hidden': section !== 'tasks' }"
    data-testid="section-body-tasks"
  >
    <slot />
  </div>

  <!-- Loaded only when opened: the portal is a large component and most visits
       to the group page are for tasks. -->
  <section
    v-if="section === 'submission'"
    class="group-section-body"
    data-testid="section-body-submission"
  >
    <GroupSubmissionPage />
  </section>
</template>

<script setup lang="ts">
/** The group page's section switcher: Tasks and Chat (the slot) and Submission. */
import { computed, defineAsyncComponent } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// Must stay unique across the route table: vue-router does not warn on a
// duplicate name, it deletes the earlier record.
const SUBMISSION_ROUTE = 'group-submission'

const GroupSubmissionPage = defineAsyncComponent(
  () => import('@/views/GroupSubmissionPage.vue'),
)

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const canSeeSubmission = computed(() => auth.isStudent)

const groupId = computed(() => String(route.params.id ?? ''))

/** Which section is showing, from the route so a refresh holds its place. */
const section = computed(() =>
  route.name === SUBMISSION_ROUTE && canSeeSubmission.value ? 'submission' : 'tasks',
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

/* Deliberately the same shape as the group page's own .tab-btn, but its own
   class: that one is a mobile-only control and these are shown at every width. */
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

/* `contents` keeps the page's panes as direct flex children of .group-detail;
   a real box would break .split's `flex: 1 1 auto` sizing. */
.group-section-slot {
  display: contents;
}

.group-section-slot.is-hidden {
  display: none;
}

/* .group-detail is a fixed height with overflow hidden on desktop, so this long
   form has to do its own scrolling. */
.group-section-body {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
}
</style>
