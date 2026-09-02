<template>
  <div>
    <p v-if="isLoading" class="component-marking__hint">Loading…</p>

    <div v-else-if="loadError" class="card component-marking__error">
      <p>Failed to load group {{ groupId }}.</p>
      <p class="component-marking__error-detail">{{ loadError }}</p>
      <div class="component-marking__error-actions">
        <button type="button" class="btn btn-outline btn-sm" @click="load">Try again</button>
        <RouterLink :to="`/grading/components/${code}`" class="btn btn-outline btn-sm">
          Back to list
        </RouterLink>
      </div>
    </div>

    <div v-else-if="payload && !block" class="card component-marking__error">
      <p>No such component "{{ code }}" for this group.</p>
      <RouterLink :to="`/grading/components/${code}`" class="btn btn-outline btn-sm">
        Back to list
      </RouterLink>
    </div>

    <div v-else-if="payload && block" class="component-marking">
      <div class="component-marking__header">
        <h2 class="component-marking__title">
          {{ payload.group.group_name }}
          <span class="component-marking__id">#{{ groupId }}</span>
        </h2>
        <div class="component-marking__nav">
          <button
            type="button"
            class="btn btn-outline btn-sm"
            :disabled="prevId == null"
            @click="goto(prevId)"
          >
            <i class="fas fa-chevron-left" aria-hidden="true"></i> Prev
          </button>
          <button
            type="button"
            class="btn btn-outline btn-sm"
            :disabled="nextId == null"
            @click="goto(nextId)"
          >
            Next <i class="fas fa-chevron-right" aria-hidden="true"></i>
          </button>
        </div>
      </div>

      <div class="component-marking__tabs" role="tablist" aria-label="Components">
        <button
          v-for="b in payload.components"
          :key="b.component.code"
          type="button"
          role="tab"
          :aria-selected="b.component.code === code"
          class="component-marking__tab"
          :class="{ active: b.component.code === code }"
          @click="switchComponent(b.component.code)"
        >
          {{ b.component.name }}
        </button>
      </div>

      <p v-if="actionError" class="component-marking__banner component-marking__banner--error">
        {{ actionError }}
      </p>
      <p v-if="saveStatus === 'saved'" class="component-marking__banner component-marking__banner--ok">
        Marks saved.
      </p>

      <ResizableSplit v-if="block.submission" right-max="23rem">
        <template #left>
          <SubmissionPreview
            :submission="block.submission"
            :component="block.component"
            :last-grader-name="currentRow?.last_grader_name"
            :grader-names="currentRow?.grader_names"
            :criterion-markers="criterionMarkers"
          />
        </template>
        <template #right>
          <RubricForm
            :submission="block.submission"
            :criteria="block.criteria"
            :grades="block.grades"
            :overall-comment-label="overallCommentLabel(block.component.code)"
            :is-saving="saveStatus === 'saving'"
            @save="saveMarks"
          >
            <template #actions>
              <RouterLink :to="`/grading/components/${code}`" class="btn btn-outline btn-sm">
                Back
              </RouterLink>
            </template>
          </RubricForm>
        </template>
      </ResizableSplit>
      <SubmissionPreview
        v-else
        :submission="block.submission"
        :component="block.component"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ResizableSplit from '@/components/grading/ResizableSplit.vue'
import RubricForm from '@/components/grading/RubricForm.vue'
import SubmissionPreview from '@/components/grading/SubmissionPreview.vue'
import {
  fetchComponentRows,
  fetchGroupMarking,
  overallCommentLabel,
  saveGradesBulk,
  type ComponentListPayload,
  type GradeBulkItem,
  type GroupMarkingPayload
} from '@/utils/gradingAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'

const route = useRoute()
const router = useRouter()
const code = computed(() => String(route.params.code || ''))
const groupId = computed(() => Number(route.params.groupId))

const payload = ref<GroupMarkingPayload | null>(null)
const rows = ref<ComponentListPayload | null>(null)
const isLoading = ref(false)
const loadError = ref('')
const actionError = ref('')
const saveStatus = ref<'idle' | 'saving' | 'saved'>('idle')

const block = computed(
  () => payload.value?.components.find((b) => b.component.code === code.value) ?? null
)

const currentRow = computed(
  () => rows.value?.rows.find((r) => r.group_id === groupId.value) ?? null
)

// Who last marked each rubric criterion of this section (tooltip lines).
const criterionMarkers = computed(() => {
  const b = block.value
  if (!b) return []
  const byCriterion = new Map(b.grades.map((g) => [g.criterion, g]))
  // Numbered by rubric position (1-based), not the full criterion text.
  return b.criteria.flatMap((c, i) => {
    const grade = byCriterion.get(c.id)
    return grade?.mark != null && grade.graded_by_name
      ? [{ name: String(i + 1), marker: grade.graded_by_name }]
      : []
  })
})

// Prev/next walk the cohort in group-ID order (matching the #id in the
// heading), skipping groups without a submission — no point navigating to an
// empty marking pane.
const orderedRows = computed(() =>
  (rows.value?.rows ?? []).slice().sort((a, b) => a.group_id - b.group_id)
)

const prevId = computed(() => {
  const list = orderedRows.value
  const idx = list.findIndex((r) => r.group_id === groupId.value)
  if (idx < 0) return null
  const back = list
    .slice(0, idx)
    .reverse()
    .find((r) => r.submission_id != null)
  return back?.group_id ?? null
})

const nextId = computed(() => {
  const list = orderedRows.value
  const idx = list.findIndex((r) => r.group_id === groupId.value)
  if (idx < 0) return null
  const fwd = list.slice(idx + 1).find((r) => r.submission_id != null)
  return fwd?.group_id ?? null
})

const load = async () => {
  if (!code.value || !Number.isFinite(groupId.value) || groupId.value <= 0) return
  isLoading.value = true
  loadError.value = ''
  try {
    // Rows drive prev/next and marker info; the group payload drives the pane.
    const [groupPayload, rowsPayload] = await Promise.all([
      fetchGroupMarking(groupId.value),
      fetchComponentRows(code.value)
    ])
    payload.value = groupPayload
    rows.value = rowsPayload
  } catch (err) {
    payload.value = null
    loadError.value = apiErrorFromUnknown(err).message
  } finally {
    isLoading.value = false
  }
}

watch(
  () => [code.value, groupId.value],
  () => {
    saveStatus.value = 'idle'
    actionError.value = ''
    void load()
  },
  { immediate: true }
)

const goto = (id: number | null) => {
  if (id == null) return
  void router.push(`/grading/components/${code.value}/${id}`)
}

const switchComponent = (target: string) => {
  if (target === code.value) return
  void router.push(`/grading/components/${target}/${groupId.value}`)
}

const saveMarks = async (items: GradeBulkItem[], overallComment: string | null) => {
  saveStatus.value = 'saving'
  actionError.value = ''
  try {
    const submissionId = block.value?.submission?.id
    await saveGradesBulk(
      items,
      overallComment !== null && submissionId != null
        ? [{ submission: submissionId, component: code.value, comment: overallComment }]
        : undefined
    )
    // Refetch both: grades for the form, rows for progress + marker columns.
    const [groupPayload, rowsPayload] = await Promise.all([
      fetchGroupMarking(groupId.value),
      fetchComponentRows(code.value)
    ])
    payload.value = groupPayload
    rows.value = rowsPayload
    saveStatus.value = 'saved'
  } catch (err) {
    saveStatus.value = 'idle'
    actionError.value = `Save failed: ${apiErrorFromUnknown(err).message}`
  }
}
</script>

<style scoped>
.component-marking__hint {
  color: var(--text-muted);
  font-size: 0.9rem;
}

.component-marking__error p {
  margin: 0 0 0.5rem;
}

.component-marking__error-detail {
  color: var(--text-muted);
  font-size: 0.85rem;
}

.component-marking__error-actions {
  display: flex;
  gap: 0.5rem;
}

.component-marking {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.component-marking__header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.component-marking__title {
  margin: 0;
  font-size: 1.35rem;
}

.component-marking__id {
  color: var(--text-muted);
  font-size: 1.35rem;
  font-weight: 400;
}

.component-marking__nav {
  display: flex;
  gap: 0.35rem;
}

/* Soft green fill lifts Prev/Next off the page without competing with the
   solid-green primary actions (Save marks). */
.component-marking__nav .btn {
  background: var(--accent-green-soft);
  border-color: var(--dark-green);
  color: var(--dark-green);
}

.component-marking__nav .btn:hover:not(:disabled) {
  background: var(--dark-green);
  color: #fff;
}

.component-marking__nav .btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

/* Segmented pill switcher, matching the Events page view tabs. */
.component-marking__tabs {
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

.component-marking__tab {
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

.component-marking__tab:hover:not(.active) {
  color: var(--charcoal);
  background: var(--accent-green-soft);
}

.component-marking__tab.active {
  background: var(--dark-green);
  color: #fff;
  box-shadow: 0 1px 3px rgba(1, 113, 81, 0.3);
}

.component-marking__banner {
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  margin: 0;
}

.component-marking__banner--error {
  background: color-mix(in srgb, var(--danger) 12%, transparent);
  color: var(--danger);
}

.component-marking__banner--ok {
  background: var(--accent-green-soft);
  color: var(--dark-green);
}

</style>
