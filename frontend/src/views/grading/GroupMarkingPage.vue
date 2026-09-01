<template>
  <div>
    <p v-if="isLoading" class="group-marking__hint">Loading marking payload…</p>

    <div v-else-if="loadError" class="card group-marking__error">
      <p>Failed to load marking payload for group {{ groupId }}.</p>
      <p class="group-marking__error-detail">{{ loadError }}</p>
      <div class="group-marking__error-actions">
        <button type="button" class="btn btn-outline btn-sm" @click="load">Try again</button>
        <RouterLink to="/grading/by-group" class="btn btn-outline btn-sm">Back</RouterLink>
      </div>
    </div>

    <div v-else-if="payload" class="group-marking">
      <div class="card group-marking__jump-card">
        <p class="group-marking__jump-hint">Enter the group's ID.</p>
        <form class="group-marking__jump" @submit.prevent="jump">
          <div class="group-marking__jump-wrap">
            <i class="fas fa-magnifying-glass group-marking__jump-icon" aria-hidden="true"></i>
            <input
              v-model="jumpId"
              type="number"
              min="1"
              placeholder="Group ID"
              class="group-marking__jump-input"
              aria-label="Group ID"
            />
          </div>
          <button type="submit" class="btn btn-primary btn-sm">Open</button>
        </form>
      </div>

      <div class="group-marking__header">
        <h2 class="group-marking__title">
          {{ payload.group.group_name }}
          <span class="group-marking__id">#{{ groupId }}</span>
        </h2>
        <div class="group-marking__header-actions">
          <button
            type="button"
            class="btn btn-outline btn-sm group-marking__nav-btn"
            :disabled="prevId == null"
            @click="goto(prevId)"
          >
            <i class="fas fa-chevron-left" aria-hidden="true"></i> Prev
          </button>
          <button
            type="button"
            class="btn btn-outline btn-sm group-marking__nav-btn"
            :disabled="nextId == null"
            @click="goto(nextId)"
          >
            Next <i class="fas fa-chevron-right" aria-hidden="true"></i>
          </button>
          <button
            type="button"
            class="btn btn-outline btn-sm"
            :disabled="isDownloading"
            @click="downloadAll"
          >
            <i class="fas fa-download" aria-hidden="true"></i>
            {{ isDownloading ? 'Preparing…' : 'Download all' }}
          </button>
        </div>
      </div>

      <p v-if="actionError" class="group-marking__banner group-marking__banner--error">
        {{ actionError }}
      </p>
      <p v-if="saveStatus === 'saved'" class="group-marking__banner group-marking__banner--ok">
        Marks saved.
      </p>

      <div class="group-marking__tabs" role="tablist" aria-label="Components">
        <button
          v-for="block in payload.components"
          :key="block.component.code"
          type="button"
          role="tab"
          :aria-selected="block.component.code === effectiveCode"
          class="group-marking__tab"
          :class="{ active: block.component.code === effectiveCode }"
          @click="activeCode = block.component.code"
        >
          {{ block.component.name }}
        </button>
      </div>

      <div v-if="activeBlock" class="group-marking__pane">
        <SubmissionPreview :submission="activeBlock.submission" :component="activeBlock.component" />
        <RubricForm
          :submission="activeBlock.submission"
          :criteria="activeBlock.criteria"
          :grades="activeBlock.grades"
          :is-saving="saveStatus === 'saving'"
          @save="saveMarks"
        >
          <template #actions>
            <RouterLink to="/grading/by-group" class="btn btn-outline btn-sm">Back</RouterLink>
          </template>
        </RubricForm>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import RubricForm from '@/components/grading/RubricForm.vue'
import SubmissionPreview from '@/components/grading/SubmissionPreview.vue'
import {
  downloadGroupZip,
  fetchComponentRows,
  fetchGroupMarking,
  saveGradesBulk,
  type ComponentRow,
  type GradeBulkItem,
  type GroupMarkingPayload
} from '@/utils/gradingAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'

const route = useRoute()
const router = useRouter()
const groupId = computed(() => Number(route.params.groupId))
const jumpId = ref('')

// Cohort list for prev/next. Any component's row list carries every group
// (submitted or not), so SAQ doubles as the group index for this page.
const cohort = ref<ComponentRow[]>([])

onMounted(async () => {
  try {
    // The API returns rows sorted by group name; walk prev/next in ID order
    // instead so navigation matches the #id shown in the heading.
    cohort.value = (await fetchComponentRows('SAQ')).rows
      .slice()
      .sort((a, b) => a.group_id - b.group_id)
  } catch {
    cohort.value = [] // prev/next simply stay disabled
  }
})

const prevId = computed(() => {
  const idx = cohort.value.findIndex((r) => r.group_id === groupId.value)
  return idx > 0 ? cohort.value[idx - 1].group_id : null
})

const nextId = computed(() => {
  const idx = cohort.value.findIndex((r) => r.group_id === groupId.value)
  return idx >= 0 && idx < cohort.value.length - 1 ? cohort.value[idx + 1].group_id : null
})

const goto = (id: number | null) => {
  if (id == null) return
  void router.push(`/grading/groups/${id}`)
}

const jump = () => {
  const n = Number(jumpId.value)
  if (!Number.isFinite(n) || n <= 0 || n === groupId.value) return
  jumpId.value = ''
  void router.push(`/grading/groups/${n}`)
}

const payload = ref<GroupMarkingPayload | null>(null)
const isLoading = ref(false)
const loadError = ref('')
const actionError = ref('')
const saveStatus = ref<'idle' | 'saving' | 'saved'>('idle')
const isDownloading = ref(false)
const activeCode = ref<string | null>(null)

const effectiveCode = computed(
  () => activeCode.value ?? payload.value?.components[0]?.component.code ?? null
)

const activeBlock = computed(
  () => payload.value?.components.find((b) => b.component.code === effectiveCode.value) ?? null
)

const load = async () => {
  if (!Number.isFinite(groupId.value) || groupId.value <= 0) return
  isLoading.value = true
  loadError.value = ''
  try {
    payload.value = await fetchGroupMarking(groupId.value)
  } catch (err) {
    payload.value = null
    loadError.value = apiErrorFromUnknown(err).message
  } finally {
    isLoading.value = false
  }
}

// Reload when navigating between groups; reset the tab so the first component
// shows for the new group rather than a stale selection.
watch(
  groupId,
  () => {
    activeCode.value = null
    saveStatus.value = 'idle'
    actionError.value = ''
    void load()
  },
  { immediate: true }
)

const saveMarks = async (items: GradeBulkItem[]) => {
  saveStatus.value = 'saving'
  actionError.value = ''
  try {
    await saveGradesBulk(items)
    // Refetch so grades (ids, graded_by) mirror the server after the upsert.
    payload.value = await fetchGroupMarking(groupId.value)
    saveStatus.value = 'saved'
  } catch (err) {
    saveStatus.value = 'idle'
    actionError.value = `Save failed: ${apiErrorFromUnknown(err).message}`
  }
}

const downloadAll = async () => {
  isDownloading.value = true
  actionError.value = ''
  try {
    await downloadGroupZip(groupId.value)
  } catch (err) {
    actionError.value = `Download failed: ${apiErrorFromUnknown(err).message}`
  } finally {
    isDownloading.value = false
  }
}
</script>

<style scoped>
.group-marking__hint {
  color: var(--text-muted);
  font-size: 0.9rem;
}

.group-marking__error p {
  margin: 0 0 0.5rem;
}

.group-marking__error-detail {
  color: var(--text-muted);
  font-size: 0.85rem;
}

.group-marking__error-actions {
  display: flex;
  gap: 0.5rem;
}

.group-marking {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.group-marking__jump-card {
  max-width: 36rem;
}

.group-marking__jump-hint {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin-bottom: 0.75rem;
}

.group-marking__jump {
  display: flex;
  gap: 0.5rem;
}

.group-marking__jump-wrap {
  position: relative;
  flex: 1;
}

.group-marking__jump-icon {
  position: absolute;
  left: 0.65rem;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  font-size: 0.8rem;
  pointer-events: none;
}

.group-marking__jump-input {
  width: 100%;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  padding: 0.45rem 0.6rem 0.45rem 2rem;
  font-size: 0.9rem;
  font-family: inherit;
  background: var(--surface-elevated);
  color: var(--charcoal);
}

.group-marking__jump-input:focus {
  outline: none;
  border-color: var(--dark-green);
}

/* Hide the native number spinners — IDs are typed, not stepped. */
.group-marking__jump-input {
  appearance: textfield;
  -moz-appearance: textfield;
}

.group-marking__jump-input::-webkit-inner-spin-button,
.group-marking__jump-input::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.group-marking__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.group-marking__title {
  margin: 0;
  font-size: 1.35rem;
}

.group-marking__id {
  color: var(--text-muted);
  font-size: 1.35rem;
  font-weight: 400;
}

.group-marking__header-actions {
  display: flex;
  gap: 0.5rem;
}

/* Soft green fill lifts Prev/Next off the page without competing with the
   solid-green primary actions (Save marks). Download all stays plain outline. */
.group-marking__nav-btn {
  background: var(--accent-green-soft);
  border-color: var(--dark-green);
  color: var(--dark-green);
}

.group-marking__nav-btn:hover:not(:disabled) {
  background: var(--dark-green);
  color: #fff;
}

.group-marking__header-actions .btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.group-marking__banner {
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  margin: 0;
}

.group-marking__banner--error {
  background: color-mix(in srgb, var(--danger) 12%, transparent);
  color: var(--danger);
}

.group-marking__banner--ok {
  background: var(--accent-green-soft);
  color: var(--dark-green);
}

/* Segmented pill switcher, matching the Events page view tabs. */
.group-marking__tabs {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 0.25rem;
  padding: 0.3rem;
  align-self: flex-start;
  background: var(--white);
  border: 1px solid var(--border-light);
  border-radius: 999px;
  box-shadow: 0 1px 2px var(--shadow);
}

.group-marking__tab {
  border: none;
  background: transparent;
  color: var(--text-muted);
  border-radius: 999px;
  padding: 0.5rem 1.1rem;
  font-weight: 600;
  font-size: 0.92rem;
  font-family: inherit;
  cursor: pointer;
  transition:
    color 0.18s ease,
    background-color 0.18s ease;
}

.group-marking__tab:hover:not(.active) {
  color: var(--charcoal);
  background: var(--accent-green-soft);
}

.group-marking__tab.active {
  background: var(--dark-green);
  color: #fff;
  box-shadow: 0 1px 3px rgba(1, 113, 81, 0.3);
}

.group-marking__pane {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  align-items: start;
}

@media (max-width: 900px) {
  .group-marking__pane {
    grid-template-columns: 1fr;
  }
}
</style>
