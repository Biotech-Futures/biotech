<template>
  <!-- Tabs appear only when there is a choice to make. Submissions are a
       student matter and the server refuses mentors and supervisors outright,
       so showing them a tab would only lead somewhere they cannot go. For
       everyone else this page is exactly what it was. -->
  <nav v-if="canSeeSubmission" class="group-sections" aria-label="Group sections">
    <button
      type="button"
      class="group-section-btn"
      :class="{ active: section === 'tasks' }"
      :aria-current="section === 'tasks' ? 'page' : undefined"
      data-testid="section-tab-tasks"
      @click="goToSection('tasks')"
    >
      Tasks
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

  <!-- The host page's own content. Hidden rather than destroyed: the group page
       keeps live task and chat state that a v-if would tear down and rebuild
       every time the tab changes. -->
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
/**
 * The group page's section switcher: Tasks (the page's own content, passed in
 * as the default slot) and Submission (the portal, embedded).
 *
 * This lives in its own component so that adding the submission tab costs
 * GroupDetailPage.vue an import and a pair of tags rather than a block of
 * markup, state and CSS. That file is ten thousand lines and shared with the
 * teams who own tasks and discussion, so every line we put in it is a line
 * they have to read and a place a merge can conflict.
 */
import { computed, defineAsyncComponent } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// Must stay unique across the whole route table. Two records sharing a name is
// not a warning in vue-router — registering the second deletes the first, so
// this path would stop matching at all.
const SUBMISSION_ROUTE = 'group-submission'

const GroupSubmissionPage = defineAsyncComponent(
  () => import('@/views/GroupSubmissionPage.vue'),
)

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const canSeeSubmission = computed(() => auth.isStudent)

const groupId = computed(() => String(route.params.id ?? ''))

/**
 * Which section is showing, derived from the route rather than held in a ref.
 *
 * Keeping it in the URL is what lets a refresh hold its place and an emailed
 * link point straight at the submission. The permission check is repeated here
 * so that a mentor who types the submission URL by hand gets the tasks view
 * rather than an empty page.
 */
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

/* `contents` removes this wrapper from the box tree, so the page's own panes
   stay direct flex children of .group-detail. Without it the desktop layout
   breaks: .split is `flex: 1 1 auto` inside a fixed-height container, and a
   real box here would leave it sizing against this div instead. */
.group-section-slot {
  display: contents;
}

.group-section-slot.is-hidden {
  display: none;
}

/* On desktop .group-detail is a fixed height with overflow hidden, sized for
   panes that scroll internally. The portal is a long form, so it has to do its
   own scrolling here or it would simply be cut off at the fold. */
.group-section-body {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
}
</style>
