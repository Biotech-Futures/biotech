<template>
  <div>
    <p v-if="isLoading" class="group-marking__hint">Loading marking payload…</p>

    <div v-else-if="loadError" class="card group-marking__error">
      <p>Failed to load marking payload for group {{ groupId }}.</p>
      <p class="group-marking__error-detail">{{ loadError }}</p>
      <div class="group-marking__error-actions">
        <button type="button" class="btn btn-outline btn-sm" @click="load">Try again</button>
        <RouterLink :to="backTarget" class="btn btn-outline btn-sm">Back</RouterLink>
      </div>
    </div>

    <div
      v-else-if="payload && isComponentMode && !activeBlock && !isCombined"
      class="card group-marking__error"
    >
      <p>No such component "{{ code }}" for this group.</p>
      <RouterLink :to="backTarget" class="btn btn-outline btn-sm">Back to list</RouterLink>
    </div>

    <div v-else-if="payload" class="group-marking">
      <div v-if="!isComponentMode" class="card group-marking__jump-card">
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
            v-if="!isComponentMode"
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
          v-if="combinedAvailable"
          type="button"
          role="tab"
          :aria-selected="isCombined"
          class="group-marking__tab"
          :class="{ active: isCombined }"
          @click="switchTab(COMBINED_CODE)"
        >
          SAQs &amp; Poster
        </button>
        <button
          v-for="block in payload.components"
          :key="block.component.code"
          type="button"
          role="tab"
          :aria-selected="block.component.code === effectiveCode"
          class="group-marking__tab"
          :class="{ active: block.component.code === effectiveCode }"
          @click="switchTab(block.component.code)"
        >
          {{ block.component.name }}
        </button>
      </div>

      <!-- Combined section: SAQ answers | poster PDF | both rubrics. The
           shared "Submitted" line sits above the split so every column
           starts at the same height beneath it. -->
      <ResizableSplit v-if="isCombined && saqBlock && posterBlock" right-max="23rem">
        <template #left>
          <div>
            <!-- The stamp row lives inside the left pane so its actions hug
                 the PDF's right edge, tracking the divider when dragged. -->
            <p class="group-marking__pane-stamp">
              <span v-if="combinedSubmittedLabel">
                Submitted {{ combinedSubmittedLabel }}<template v-if="combinedIsLate"> (late)</template>
                <template v-if="combinedMarkerText">
                  · Marker:
                  <span class="group-marking__stamp-marker" :title="combinedMarkerTooltip">
                    {{ combinedMarkerText }}
                  </span>
                </template>
                <span
                  v-if="categoriesStatus"
                  class="group-marking__stamp-status"
                  :class="{ 'is-error': categoriesStatus.error }"
                >
                  · {{ categoriesStatus.text }}
                </span>
              </span>
              <span v-if="posterLinks.previewable" class="group-marking__stamp-actions">
                <span class="group-marking__stamp-actions-label">Poster PDF:</span>
                <a
                  :href="posterLinks.view ?? undefined"
                  target="_blank"
                  rel="noreferrer"
                  class="btn btn-outline btn-sm"
                >
                  Open <i class="fas fa-arrow-up-right-from-square" aria-hidden="true"></i>
                </a>
                <a
                  v-if="posterLinks.download"
                  :href="posterLinks.download"
                  class="btn btn-outline btn-sm"
                  :download="posterBlock.submission?.file_name ?? ''"
                >
                  Download <i class="fas fa-download" aria-hidden="true"></i>
                </a>
              </span>
            </p>
            <!-- Category boxes span above the nested split, so the answers
                 AND the pdf both start below them. -->
            <MarkingCategories :group-id="groupId" @status="categoriesStatus = $event" />
            <!-- Nested split: drag the divider to trade space between the
                 answers and the poster. -->
            <ResizableSplit>
              <template #left>
                <SubmissionPreview
                  :submission="saqBlock.submission"
                  :component="saqBlock.component"
                  :last-grader-name="saqBlock.last_grader_name"
                  :criterion-markers="markersFor(saqBlock)"
                  hide-submitted
                />
              </template>
              <template #right>
                <SubmissionPreview
                  :submission="posterBlock.submission"
                  :component="posterBlock.component"
                  :last-grader-name="posterBlock.last_grader_name"
                  :criterion-markers="markersFor(posterBlock)"
                  hide-submitted
                />
              </template>
            </ResizableSplit>
          </div>
        </template>
        <template #right>
          <div class="group-marking__combined-rubrics group-marking__pane-offset">
            <div>
              <h4 class="group-marking__rubric-title">{{ saqBlock.component.name }}</h4>
              <RubricForm
                ref="saqForm"
                :submission="saqBlock.submission"
                :criteria="saqBlock.criteria"
                :grades="saqBlock.grades"
                :overall-comment-label="overallCommentLabel(saqBlock.component.code)"
                :is-saving="saveStatus === 'saving'"
                @save="saveSaqMarks"
              />
            </div>
            <div>
              <h4 class="group-marking__rubric-title">{{ posterBlock.component.name }}</h4>
              <RubricForm
                ref="posterForm"
                :submission="posterBlock.submission"
                :criteria="posterBlock.criteria"
                :grades="posterBlock.grades"
                :overall-comment-label="overallCommentLabel(posterBlock.component.code)"
                :is-saving="saveStatus === 'saving'"
                @save="savePosterMarks"
              />
            </div>
            <RouterLink :to="backTarget" class="btn btn-outline btn-sm group-marking__back">
              Back
            </RouterLink>
          </div>
        </template>
      </ResizableSplit>
      <template v-else-if="activeBlock">
        <ResizableSplit v-if="activeBlock.submission" right-max="23rem">
          <template #left>
            <div>
              <!-- Stamp row inside the pane: actions hug the preview's right
                   edge; the rubric column offsets to stay level below. -->
              <p class="group-marking__pane-stamp">
                <span>
                  Submitted {{ singleSubmittedLabel
                  }}<template v-if="activeBlock.submission.is_late"> (late)</template>
                  <template v-if="singleMarkerName">
                    · Marker:
                    <span class="group-marking__stamp-marker" :title="singleMarkerTooltip">
                      {{ singleMarkerName }}
                      <i
                        v-if="(singleGraderNames?.length ?? 0) > 1"
                        class="fas fa-users group-marking__stamp-marker-icon"
                        aria-hidden="true"
                      ></i>
                    </span>
                  </template>
                  <span
                    v-if="categoriesStatus && activeBlock.component.code === 'SAQ'"
                    class="group-marking__stamp-status"
                    :class="{ 'is-error': categoriesStatus.error }"
                  >
                    · {{ categoriesStatus.text }}
                  </span>
                </span>
                <span v-if="singleLinks.previewable" class="group-marking__stamp-actions">
                  <a
                    :href="singleLinks.view ?? undefined"
                    target="_blank"
                    rel="noreferrer"
                    class="btn btn-outline btn-sm"
                  >
                    Open <i class="fas fa-arrow-up-right-from-square" aria-hidden="true"></i>
                  </a>
                  <a
                    v-if="singleLinks.download"
                    :href="singleLinks.download"
                    class="btn btn-outline btn-sm"
                    :download="activeBlock.submission.file_name ?? ''"
                  >
                    Download <i class="fas fa-download" aria-hidden="true"></i>
                  </a>
                </span>
              </p>
              <MarkingCategories
                v-if="activeBlock.component.code === 'SAQ'"
                :group-id="groupId"
                @status="categoriesStatus = $event"
              />
              <SubmissionPreview
                :submission="activeBlock.submission"
                :component="activeBlock.component"
                :criterion-markers="criterionMarkers"
                hide-submitted
              />
            </div>
          </template>
          <template #right>
            <div class="group-marking__pane-offset">
              <RubricForm
                ref="rubricForm"
                :submission="activeBlock.submission"
                :criteria="activeBlock.criteria"
                :grades="activeBlock.grades"
                :overall-comment-label="overallCommentLabel(activeBlock.component.code)"
                :is-saving="saveStatus === 'saving'"
                @save="saveMarks"
              >
                <template #actions>
                  <RouterLink :to="backTarget" class="btn btn-outline btn-sm">Back</RouterLink>
                </template>
              </RubricForm>
            </div>
          </template>
        </ResizableSplit>
        <SubmissionPreview
          v-else
          :submission="activeBlock.submission"
          :component="activeBlock.component"
          :last-grader-name="activeBlock.last_grader_name"
          :criterion-markers="criterionMarkers"
        />
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { markingFullWidth } from '@/composables/markingLayout'
import MarkingCategories from '@/components/grading/MarkingCategories.vue'
import ResizableSplit from '@/components/grading/ResizableSplit.vue'
import RubricForm from '@/components/grading/RubricForm.vue'
import SubmissionPreview from '@/components/grading/SubmissionPreview.vue'
import {
  downloadGroupZip,
  fetchComponentRows,
  fetchGroupMarking,
  overallCommentLabel,
  resolveApiFileUrl,
  saveGradesBulk,
  type ComponentListPayload,
  type GradeBulkItem,
  type GroupMarkingPayload
} from '@/utils/gradingAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'

// One page serves both marking flows; the route decides the chrome. By group
// (/grading/groups/:id) gets the jump card and Download all, and switches
// sections locally. By component (/grading/components/:code/:id) hides those
// extras and navigates its sections through the URL, so a marker can walk
// groups without leaving their component.
const route = useRoute()
const router = useRouter()
const isComponentMode = computed(() => route.name === 'grading-component-group')
const code = computed(() => String(route.params.code || ''))
const groupId = computed(() => Number(route.params.groupId))
const jumpId = ref('')

type ComponentBlock = GroupMarkingPayload['components'][number]

// Synthetic first tab: the SAQ answers and the poster marked side by side.
const COMBINED_CODE = 'SAQ_POSTER'

const payload = ref<GroupMarkingPayload | null>(null)
const rows = ref<ComponentListPayload | null>(null)
const isLoading = ref(false)
const loadError = ref('')
const actionError = ref('')
const saveStatus = ref<'idle' | 'saving' | 'saved'>('idle')
const isDownloading = ref(false)
const activeCode = ref<string | null>(null)
const rubricForm = ref<InstanceType<typeof RubricForm> | null>(null)
const saqForm = ref<InstanceType<typeof RubricForm> | null>(null)
const posterForm = ref<InstanceType<typeof RubricForm> | null>(null)

const saqBlock = computed<ComponentBlock | null>(
  () => payload.value?.components.find((b) => b.component.code === 'SAQ') ?? null
)
const posterBlock = computed<ComponentBlock | null>(
  () => payload.value?.components.find((b) => b.component.code === 'POSTER') ?? null
)
const combinedAvailable = computed(() => saqBlock.value != null && posterBlock.value != null)

const effectiveCode = computed(() =>
  isComponentMode.value
    ? code.value
    : (activeCode.value ??
      (combinedAvailable.value
        ? COMBINED_CODE
        : (payload.value?.components[0]?.component.code ?? null)))
)

const isCombined = computed(() => effectiveCode.value === COMBINED_CODE)

// Categories save-state, surfaced on the "Submitted" line rather than in
// the boxes themselves; cleared whenever the section or group changes.
const categoriesStatus = ref<{ text: string; error: boolean } | null>(null)

// Full browser width for the pdf/answer splits; Prototype (a link + zip)
// doesn't need it and keeps the normal centred layout.
watch(
  effectiveCode,
  (code) => {
    markingFullWidth.value = code != null && code !== 'PROTOTYPE'
    categoriesStatus.value = null
  },
  { immediate: true }
)
onBeforeUnmount(() => {
  markingFullWidth.value = false
})

const activeBlock = computed(
  () => payload.value?.components.find((b) => b.component.code === effectiveCode.value) ?? null
)

// Rows (prev/next, marker columns) need a real component; SAQ stands in for
// the combined tab and for by-group mode — any component's rows carry the
// whole cohort.
const rowsCode = computed(() =>
  isComponentMode.value && !isCombined.value ? code.value : 'SAQ'
)

const currentRow = computed(
  () => rows.value?.rows.find((r) => r.group_id === groupId.value) ?? null
)

const backTarget = computed(() =>
  isComponentMode.value ? `/grading/components/${rowsCode.value}` : '/grading/by-group'
)

// Tab switches in by-group mode swap the forms' props in place, silently
// discarding edits — route guards don't fire there, so ask every mounted
// form first. Component mode navigates, so the forms guard themselves.
const anyFormDirty = () =>
  Boolean(rubricForm.value?.isDirty || saqForm.value?.isDirty || posterForm.value?.isDirty)

const switchTab = (target: string) => {
  if (target === effectiveCode.value) return
  if (isComponentMode.value) {
    void router.push(`/grading/components/${target}/${groupId.value}`)
    return
  }
  if (
    anyFormDirty() &&
    !window.confirm('You have unsaved marks or comments. Switch section without saving?')
  ) {
    return
  }
  activeCode.value = target
}

// Who last marked each rubric criterion of a section (tooltip lines).
// Numbered by rubric position (1-based), not the full criterion text.
const markersFor = (block: ComponentBlock) => {
  const byCriterion = new Map(block.grades.map((g) => [g.criterion, g]))
  return block.criteria.flatMap((c, i) => {
    const grade = byCriterion.get(c.id)
    return grade?.mark != null && grade.graded_by_name
      ? [{ name: String(i + 1), marker: grade.graded_by_name }]
      : []
  })
}

const criterionMarkers = computed(() => (activeBlock.value ? markersFor(activeBlock.value) : []))

// Both combined sections share one Submission row, so the stamp is shown
// once above them rather than repeated per pane.
const combinedSubmission = computed(
  () => saqBlock.value?.submission ?? posterBlock.value?.submission ?? null
)
const combinedSubmittedLabel = computed(() =>
  combinedSubmission.value
    ? new Date(combinedSubmission.value.submitted_at).toLocaleString()
    : ''
)
const combinedIsLate = computed(() => combinedSubmission.value?.is_late === true)

// Last marker of each combined section; collapsed to one name when the same
// person marked both. The tooltip lists every criterion's marker.
const combinedMarkerText = computed(() => {
  const saq = saqBlock.value?.last_grader_name
  const poster = posterBlock.value?.last_grader_name
  if (saq && poster) return saq === poster ? saq : `SAQ: ${saq} · Poster: ${poster}`
  if (saq) return `SAQ: ${saq}`
  if (poster) return `Poster: ${poster}`
  return ''
})

const combinedMarkerTooltip = computed(() => {
  const lines: string[] = []
  if (saqBlock.value) {
    lines.push(...markersFor(saqBlock.value).map((m) => `SAQ ${m.name}: ${m.marker}`))
  }
  if (posterBlock.value) {
    lines.push(...markersFor(posterBlock.value).map((m) => `Poster ${m.name}: ${m.marker}`))
  }
  return lines.join('\n')
})

// Open/Download live on the hoisted stamp line. Same rules as the preview's
// own meta row: Open only for PDFs (anything else keeps its in-pane box).
const fileLinks = (submission: ComponentBlock['submission']) => {
  const view = resolveApiFileUrl(submission?.file_url ?? null)
  const download = resolveApiFileUrl(submission?.file_download_url ?? submission?.file_url ?? null)
  let previewable = false
  if (view) {
    try {
      previewable = new URL(view, window.location.origin).pathname.toLowerCase().endsWith('.pdf')
    } catch {
      previewable = false
    }
  }
  return { view, download, previewable }
}

const posterLinks = computed(() => fileLinks(posterBlock.value?.submission ?? null))
const singleLinks = computed(() => fileLinks(activeBlock.value?.submission ?? null))

// Single-tab stamp, hoisted above the split like the combined one. Marker
// info mirrors what SubmissionPreview would have shown in its own stamp.
const singleSubmittedLabel = computed(() =>
  activeBlock.value?.submission
    ? new Date(activeBlock.value.submission.submitted_at).toLocaleString()
    : ''
)
const singleMarkerName = computed(() =>
  isComponentMode.value ? currentRow.value?.last_grader_name : activeBlock.value?.last_grader_name
)
const singleGraderNames = computed(() =>
  isComponentMode.value ? currentRow.value?.grader_names : undefined
)
const singleMarkerTooltip = computed(() => {
  if (criterionMarkers.value.length) {
    return criterionMarkers.value.map((c) => `${c.name}: ${c.marker}`).join('\n')
  }
  const names = singleGraderNames.value?.length
    ? singleGraderNames.value
    : singleMarkerName.value
      ? [singleMarkerName.value]
      : []
  return names.length ? `Marked by: ${names.join(', ')}` : ''
})

// Prev/next walk the cohort in group-ID order, matching the #id in the
// heading. Component mode skips groups without a submission — no point
// navigating to an empty marking pane there.
const orderedRows = computed(() =>
  (rows.value?.rows ?? []).slice().sort((a, b) => a.group_id - b.group_id)
)

const neighborId = (direction: -1 | 1) => {
  const list = orderedRows.value
  const idx = list.findIndex((r) => r.group_id === groupId.value)
  if (idx < 0) return null
  const candidates = direction === -1 ? list.slice(0, idx).reverse() : list.slice(idx + 1)
  const hit = isComponentMode.value
    ? candidates.find((r) => r.submission_id != null)
    : candidates[0]
  return hit?.group_id ?? null
}

const prevId = computed(() => neighborId(-1))
const nextId = computed(() => neighborId(1))

const goto = (id: number | null) => {
  if (id == null) return
  void router.push(
    isComponentMode.value ? `/grading/components/${code.value}/${id}` : `/grading/groups/${id}`
  )
}

const jump = () => {
  const n = Number(jumpId.value)
  if (!Number.isFinite(n) || n <= 0 || n === groupId.value) return
  jumpId.value = ''
  void router.push(`/grading/groups/${n}`)
}

const load = async () => {
  if (!Number.isFinite(groupId.value) || groupId.value <= 0) return
  if (isComponentMode.value && !code.value) return
  isLoading.value = true
  loadError.value = ''
  try {
    // Rows are best-effort: without them prev/next simply stay disabled.
    const [groupPayload, rowsPayload] = await Promise.all([
      fetchGroupMarking(groupId.value),
      fetchComponentRows(rowsCode.value).catch(() => null)
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

// Reload when navigating between groups or sections; reset the local tab so
// by-group mode shows its default section for the new group.
watch(
  () => [groupId.value, code.value, isComponentMode.value] as const,
  () => {
    activeCode.value = null
    saveStatus.value = 'idle'
    actionError.value = ''
    void load()
  },
  { immediate: true }
)

const saveMarksForBlock = async (
  block: ComponentBlock,
  items: GradeBulkItem[],
  overallComment: string | null
) => {
  saveStatus.value = 'saving'
  actionError.value = ''
  try {
    const submissionId = block.submission?.id
    const componentCode = block.component.code
    await saveGradesBulk(
      items,
      overallComment !== null && submissionId != null && componentCode
        ? [{ submission: submissionId, component: componentCode, comment: overallComment }]
        : undefined
    )
    // Refetch so grades (ids, graded_by) mirror the server after the upsert.
    // In the combined view the other section's form keeps its unsaved edits
    // across this — RubricForm preserves dirty rows for the same entry.
    const [groupPayload, rowsPayload] = await Promise.all([
      fetchGroupMarking(groupId.value),
      fetchComponentRows(rowsCode.value).catch(() => null)
    ])
    payload.value = groupPayload
    rows.value = rowsPayload
    saveStatus.value = 'saved'
  } catch (err) {
    saveStatus.value = 'idle'
    actionError.value = `Save failed: ${apiErrorFromUnknown(err).message}`
  }
}

const saveMarks = (items: GradeBulkItem[], overallComment: string | null) => {
  if (activeBlock.value) void saveMarksForBlock(activeBlock.value, items, overallComment)
}

const saveSaqMarks = (items: GradeBulkItem[], overallComment: string | null) => {
  if (saqBlock.value) void saveMarksForBlock(saqBlock.value, items, overallComment)
}

const savePosterMarks = (items: GradeBulkItem[], overallComment: string | null) => {
  if (posterBlock.value) void saveMarksForBlock(posterBlock.value, items, overallComment)
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

/* Combined SAQs & Poster section: answers | pdf side by side, rubrics stacked
   in the right pane. */
/* Top row of the left pane: "Submitted …" left, Open/Download hugging the
   preview's right edge. Fixed height so the rubric column can offset to
   start level with the content below it. */
.group-marking__pane-stamp {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
  min-height: 2rem;
  font-size: 0.85rem;
  color: var(--text-muted);
  margin: 0 0 1rem;
}

.group-marking__stamp-actions {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.group-marking__stamp-actions-label {
  color: var(--text-muted);
  font-weight: 600;
}

/* min-height + margin of the stamp row above, so the rubric column starts
   where the preview content starts. */
.group-marking__pane-offset {
  padding-top: 3rem;
}

.group-marking__stamp-marker {
  color: var(--charcoal);
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
}

.group-marking__stamp-marker-icon {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.group-marking__stamp-status {
  color: var(--dark-green);
}

.group-marking__stamp-status.is-error {
  color: var(--danger);
}

.group-marking__combined-rubrics {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  /* Scrolls within its own pane, like the answers and PDF beside it, so a
     long rubric stack doesn't stretch the page. */
  max-height: 88vh;
  overflow-y: auto;
  padding-right: 0.25rem;
}

.group-marking__rubric-title {
  margin: 0 0 0.5rem;
  font-size: 0.95rem;
  color: var(--charcoal);
}

.group-marking__back {
  align-self: flex-start;
}
</style>
