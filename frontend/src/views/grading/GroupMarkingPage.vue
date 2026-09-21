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

      <div class="group-marking__header">
        <h2 class="group-marking__title">
          {{ payload.group.group_name }}
          <span class="group-marking__id">#{{ groupId }}</span>
        </h2>
        <div class="group-marking__search-field">
          <span class="group-marking__search-label">Search</span>
          <form class="group-marking__search-form" @submit.prevent="openSearch">
            <GroupSearchInput
              ref="picker"
              v-model="searchQuery"
              class="group-marking__picker"
              @select="onSearchSelect"
            />
            <button type="submit" class="btn btn-primary btn-sm">Open</button>
            <p v-if="searchError" class="group-marking__search-error">{{ searchError }}</p>
          </form>
        </div>
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
            class="btn btn-outline btn-sm group-marking__nav-btn"
            :disabled="nextUnmarkedId == null"
            @click="goto(nextUnmarkedId)"
          >
            Next Unmarked <i class="fas fa-angles-right" aria-hidden="true"></i>
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
          <div class="group-marking__pane-offset">
          <div
            ref="rubricsEl"
            class="group-marking__combined-rubrics"
            :style="
              rubricsHeight != null ? { height: `${rubricsHeight}px`, maxHeight: 'none' } : undefined
            "
          >
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
          <div
            class="group-marking__rubrics-resize"
            role="separator"
            aria-orientation="horizontal"
            aria-label="Resize rubrics height"
            tabindex="0"
            @pointerdown="startRubricsDrag"
            @keydown="onRubricsKeydown"
          ></div>
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
import GroupSearchInput from '@/components/grading/GroupSearchInput.vue'
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

// One page serves both marking flows with the same chrome (search, prev/next,
// Download all). The route only decides section navigation: by group
// (/grading/groups/:id) switches sections locally, while by component
// (/grading/components/:code/:id) navigates them through the URL, so a marker
// can walk groups without leaving their component.
const route = useRoute()
const router = useRouter()
const isComponentMode = computed(() => route.name === 'grading-component-group')
const code = computed(() => String(route.params.code || ''))
const groupId = computed(() => Number(route.params.groupId))
const picker = ref<InstanceType<typeof GroupSearchInput> | null>(null)
const searchQuery = ref('')
const searchError = ref('')

type ComponentBlock = GroupMarkingPayload['components'][number]

// Synthetic first tab: the SAQ answers and the poster marked side by side.
const COMBINED_CODE = 'SAQ_POSTER'

// All real components — prev/next checks submissions across every one.
const ALL_CODES = ['SAQ', 'POSTER', 'REPORT', 'PROTOTYPE']

const payload = ref<GroupMarkingPayload | null>(null)
const rows = ref<ComponentListPayload | null>(null)
const allRows = ref<ComponentListPayload[]>([])
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
// heading. A group is skipped only when it has no submission in ANY
// component; submitting any one component keeps it reachable.
const orderedGroupIds = computed(() => {
  const ids = new Set<number>()
  for (const p of allRows.value) for (const r of p.rows) ids.add(r.group_id)
  return [...ids].sort((a, b) => a - b)
})

const groupsWithSubmission = computed(() => {
  const ids = new Set<number>()
  for (const p of allRows.value) {
    for (const r of p.rows) if (r.submission_id != null) ids.add(r.group_id)
  }
  return ids
})

const neighborId = (direction: -1 | 1) => {
  const list = orderedGroupIds.value
  const idx = list.indexOf(groupId.value)
  if (idx < 0) return null
  const candidates = direction === -1 ? list.slice(0, idx).reverse() : list.slice(idx + 1)
  return candidates.find((id) => groupsWithSubmission.value.has(id)) ?? null
}

const prevId = computed(() => neighborId(-1))
const nextId = computed(() => neighborId(1))

// "Next Unmarked" walks forward (wrapping past the last ID to the first)
// to the next group whose CURRENT subtab still has unmarked rubric criteria.
// Groups whose rubric here is fully marked are skipped, as are groups with
// nothing to mark on this subtab (no submission, or no rubric defined).
const activeMarkingCodes = computed(() =>
  isCombined.value ? ['SAQ', 'POSTER'] : effectiveCode.value ? [effectiveCode.value] : []
)

const hasUnmarkedHere = (id: number) =>
  activeMarkingCodes.value.some((markingCode) => {
    const p = allRows.value.find((x) => x.component.code === markingCode)
    if (!p || p.criteria_total <= 0) return false
    const r = p.rows.find((row) => row.group_id === id)
    return r != null && r.submission_id != null && r.criteria_graded < p.criteria_total
  })

const nextUnmarkedId = computed(() => {
  const list = orderedGroupIds.value
  if (!list.length) return null
  const idx = list.indexOf(groupId.value)
  const start = idx < 0 ? -1 : idx
  for (let step = 1; step <= list.length; step++) {
    const candidate = list[(start + step + list.length) % list.length]
    if (candidate === groupId.value) continue
    if (hasUnmarkedHere(candidate)) return candidate
  }
  return null
})

const goto = (id: number | null) => {
  if (id == null) return
  void router.push(
    isComponentMode.value ? `/grading/components/${code.value}/${id}` : `/grading/groups/${id}`
  )
}

// Same search box as the marking tables; Open resolves the typed name or ID
// and navigates within the current mode (component or by-group).
const openSearch = () => {
  searchError.value = ''
  const id = picker.value?.resolveId() ?? null
  if (id == null) {
    searchError.value = 'No group matches that name or ID.'
    return
  }
  searchQuery.value = ''
  if (id !== groupId.value) goto(id)
}

// Picking a dropdown suggestion navigates straight away.
const onSearchSelect = ({ id }: { id: number }) => {
  searchError.value = ''
  searchQuery.value = ''
  if (id !== groupId.value) goto(id)
}

// Drag the bar under the combined rubric stack to change its height — the
// same mechanic as the answer/PDF blocks in SubmissionPreview.
const MIN_RUBRICS_PX = 240
const rubricsEl = ref<HTMLDivElement | null>(null)
const rubricsHeight = ref<number | null>(null)

const startRubricsDrag = (event: PointerEvent) => {
  const el = rubricsEl.value
  const handle = event.currentTarget as HTMLElement
  if (!el) return
  event.preventDefault()
  handle.setPointerCapture(event.pointerId)
  const startY = event.clientY
  const startHeight = el.getBoundingClientRect().height

  const move = (e: PointerEvent) => {
    rubricsHeight.value = Math.max(MIN_RUBRICS_PX, Math.round(startHeight + (e.clientY - startY)))
  }
  const stop = () => {
    handle.removeEventListener('pointermove', move)
    handle.removeEventListener('pointerup', stop)
    handle.removeEventListener('pointercancel', stop)
  }
  handle.addEventListener('pointermove', move)
  handle.addEventListener('pointerup', stop)
  handle.addEventListener('pointercancel', stop)
}

const onRubricsKeydown = (e: KeyboardEvent) => {
  const current = rubricsHeight.value ?? rubricsEl.value?.getBoundingClientRect().height ?? 0
  if (e.key === 'ArrowDown') {
    rubricsHeight.value = Math.round(current + 40)
    e.preventDefault()
  } else if (e.key === 'ArrowUp') {
    rubricsHeight.value = Math.max(MIN_RUBRICS_PX, Math.round(current - 40))
    e.preventDefault()
  }
}

const load = async () => {
  if (!Number.isFinite(groupId.value) || groupId.value <= 0) return
  if (isComponentMode.value && !code.value) return
  isLoading.value = true
  loadError.value = ''
  try {
    // Rows are best-effort: without them prev/next simply stay disabled.
    // Every component's rows load so prev/next can spot a submission in any
    // of them; the current component's rows also feed the marker columns.
    const [groupPayload, componentRows] = await Promise.all([
      fetchGroupMarking(groupId.value),
      Promise.all(ALL_CODES.map((c) => fetchComponentRows(c).catch(() => null)))
    ])
    payload.value = groupPayload
    allRows.value = componentRows.filter((p): p is ComponentListPayload => p != null)
    rows.value = allRows.value.find((p) => p.component.code === rowsCode.value) ?? null
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

/* Search sits centered in the header row, between the title and the Prev/
   Next/Download buttons. The error overlays below so it never stretches
   the row. */
/* Unlike the table pages, the label sits inline, left of the textbox. */
.group-marking__search-field {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-inline: auto;
}

.group-marking__search-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.group-marking__search-form {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

/* Same width as the By Component page's search box. */
.group-marking__picker {
  width: 252px;
}

.group-marking__search-error {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  color: var(--danger);
  font-size: 0.85rem;
  margin: 0;
  white-space: nowrap;
}

.group-marking__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
  /* A little extra breathing room above the marking content. */
  margin-bottom: 0.85rem;
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
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
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
  max-height: 94vh;
  overflow-y: auto;
  padding-right: 0.25rem;
}

/* Same drag bar as the preview blocks in SubmissionPreview. */
.group-marking__rubrics-resize {
  height: 4px;
  width: 100%;
  margin: 0.15rem 0 0;
  border-radius: 999px;
  background: var(--border-light);
  cursor: row-resize;
  touch-action: none;
}

.group-marking__rubrics-resize:hover,
.group-marking__rubrics-resize:active {
  background: var(--dark-green);
}

.group-marking__rubrics-resize:focus-visible {
  outline: 2px solid var(--dark-green);
  outline-offset: 2px;
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
