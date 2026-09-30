<template>
  <div v-if="submission">
    <div v-if="criteria.length === 0 && !overallCommentLabel" class="rubric-form__empty">
      No rubric defined for this component yet. Add criteria in the Django admin
      rubric editor, then reload.
    </div>

    <form v-else class="rubric-form" @submit.prevent="handleSubmit">
      <div v-for="c in criteria" :key="c.id" class="rubric-form__criterion">
        <!-- The most first, floated right, so the criterion's words run on
             under it rather than leaving a column empty beneath it. -->
        <div class="rubric-form__criterion-head">
          <span class="rubric-form__max">/ {{ c.max_mark }}</span>
          <p class="rubric-form__name">{{ c.name }}</p>
        </div>
        <div class="rubric-form__fields">
          <input
            type="number"
            inputmode="decimal"
            step="0.01"
            min="0"
            :max="c.max_mark"
            placeholder="Mark"
            class="rubric-form__mark"
            :value="state[c.id]?.mark ?? ''"
            @input="onMarkInput(c.id, $event.target as HTMLInputElement)"
          />
          <textarea
            placeholder="Comment (optional)"
            rows="2"
            class="rubric-form__comment"
            :value="state[c.id]?.comment ?? ''"
            @input="setComment(c.id, ($event.target as HTMLTextAreaElement).value)"
          ></textarea>
        </div>
      </div>

      <div v-if="overallCommentLabel" class="rubric-form__criterion rubric-form__overall">
        <p class="rubric-form__name">{{ overallCommentLabel }}</p>
        <textarea
          v-model="overallComment"
          placeholder="Overall feedback on this submission (optional)"
          rows="3"
          class="rubric-form__comment rubric-form__overall-input"
        ></textarea>
      </div>

      <div class="rubric-form__actions">
        <slot name="actions"></slot>
        <button type="submit" class="btn btn-primary btn-sm" :disabled="isSaving || !isDirty">
          {{ isSaving ? 'Saving…' : 'Save' }}
        </button>
      </div>
    </form>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import type {
  Grade,
  GradeBulkItem,
  OverallCommentEdit,
  RubricCriterion,
  Submission
} from '@/utils/gradingAPI'

const props = defineProps<{
  submission: Submission | null
  criteria: RubricCriterion[]
  grades: Grade[]
  isSaving: boolean
  /** Heading for the overall-comment box; omit/null to hide it (e.g. SAQ). */
  overallCommentLabel?: string | null
  /** Unsaved edits outside this form that its Save button also stores (the
   *  SAQ category boxes). Enables Save and the leave guards like own edits. */
  extraDirty?: boolean
}>()

const emit = defineEmits<{
  /** Only the rows edited here; the overall comment is null when it wasn't
   *  edited, or its box is hidden for this component. */
  save: [items: GradeBulkItem[], overallComment: OverallCommentEdit | null]
}>()

type FormRow = { mark: string; comment: string }

const state = reactive<Record<number, FormRow>>({})
const overallComment = ref('')
// What each row started from: as loaded, or as another marker has since left
// it, for a row not touched here. A row is an edit only when it differs from
// this, and a save names it, so the server can refuse a save over another
// marker's change rather than write stale values over it.
const base = reactive<Record<number, FormRow>>({})
const baseOverall = ref('')

// "5" and "5.00" are the same mark — the server normalises decimals, so a
// plain string compare would flag a just-saved value as an edit.
const sameMark = (a: string, b: string) => {
  if (a.trim() === b.trim()) return true
  if (a.trim() === '' || b.trim() === '') return false
  const na = Number(a)
  const nb = Number(b)
  return Number.isFinite(na) && Number.isFinite(nb) && na === nb
}

const sameRow = (a: FormRow, b: FormRow) => sameMark(a.mark, b.mark) && a.comment === b.comment
const edited = (criterionId: number) => {
  const row = state[criterionId]
  const was = base[criterionId]
  return row != null && was != null && !sameRow(row, was)
}

// Preload form state from existing grades keyed by criterion id, with empty
// defaults for un-graded criteria. Re-runs when the payload refetches after a
// save round-trip. A refetch of the SAME entry (e.g. the combined SAQs &
// Poster view saving the other section) keeps edits the server doesn't hold
// yet; every other row takes the server's value, so a row left alone shows
// another marker's change instead of staying stale. A different entry resets
// everything.
let boundSubmissionId: number | null = null
watch(
  () => [props.submission, props.criteria, props.grades] as const,
  ([submission, criteria, grades]) => {
    const sameEntry = submission?.id != null && submission.id === boundSubmissionId
    boundSubmissionId = submission?.id ?? null

    const byCriterion = new Map<number, Grade>()
    for (const g of grades) byCriterion.set(g.criterion, g)
    for (const key of Object.keys(state)) {
      if (!criteria.some((c) => c.id === Number(key))) {
        delete state[Number(key)]
        delete base[Number(key)]
      }
    }
    for (const c of criteria) {
      const g = byCriterion.get(c.id)
      const server: FormRow = { mark: g?.mark ?? '', comment: g?.comment ?? '' }
      const row = state[c.id]
      const keepEdit = sameEntry && row != null && edited(c.id) && !sameRow(row, server)
      if (!keepEdit) {
        state[c.id] = { ...server }
        base[c.id] = { ...server }
      }
    }

    const serverOverall = submission?.overall_comment ?? ''
    const keepOverall =
      sameEntry && overallComment.value !== baseOverall.value && overallComment.value !== serverOverall
    if (!keepOverall) {
      overallComment.value = serverOverall
      baseOverall.value = serverOverall
    }
  },
  { immediate: true }
)

// Unsaved edits: any mark, comment, or overall comment changed from what it
// started from, or edits the parent reports via extraDirty. Retyping the
// starting value counts as clean.
const overallEdited = computed(() =>
  Boolean(props.overallCommentLabel) && overallComment.value !== baseOverall.value
)
const isDirty = computed(
  () => Boolean(props.extraDirty) || props.criteria.some((c) => edited(c.id)) || overallEdited.value
)

const UNSAVED_MESSAGE = 'You have unsaved marks or comments. Leave without saving?'

// Tab close / reload — the browser shows its own generic prompt.
const onBeforeUnload = (event: BeforeUnloadEvent) => {
  if (!isDirty.value) return
  event.preventDefault()
  event.returnValue = ''
}
window.addEventListener('beforeunload', onBeforeUnload)
onBeforeUnmount(() => window.removeEventListener('beforeunload', onBeforeUnload))

// In-app navigation: leaving the marking route, and Prev/Next (same route,
// different group id) which only fires the update guard.
const confirmLeave = () => !isDirty.value || window.confirm(UNSAVED_MESSAGE)
onBeforeRouteLeave(confirmLeave)
onBeforeRouteUpdate(confirmLeave)

// Parents guard non-route switches (e.g. the component tabs) themselves.
defineExpose({ isDirty })

const setMark = (criterionId: number, mark: string) => {
  if (state[criterionId]) state[criterionId].mark = mark
}

// At most two decimal places: a third typed (or pasted) digit is dropped.
const PAST_TWO_DECIMALS = /^(\d*\.\d{2})\d+$/
const onMarkInput = (criterionId: number, input: HTMLInputElement) => {
  const mark = input.value.replace(PAST_TWO_DECIMALS, '$1')
  if (mark !== input.value) input.value = mark
  setMark(criterionId, mark)
}

const setComment = (criterionId: number, comment: string) => {
  if (state[criterionId]) state[criterionId].comment = comment
}

// Empty -> null, so a mark reads as "not graded yet" rather than 0. Numeric
// validation is loose here: DRF's DecimalField rejects anything unparseable
// and the error surfaces to the caller.
const markOrNull = (mark: string) => (mark.trim() ? mark : null)

// Only the rows edited here, each with what it started from: rows left alone
// are never written, and the server refuses a save over another marker's
// change instead of replacing it.
const handleSubmit = () => {
  if (!props.submission) return
  const items: GradeBulkItem[] = props.criteria
    .filter((c) => edited(c.id))
    .map((c) => ({
      submission: props.submission!.id,
      criterion: c.id,
      mark: markOrNull(state[c.id]!.mark),
      comment: state[c.id]!.comment,
      expected_mark: markOrNull(base[c.id]!.mark),
      expected_comment: base[c.id]!.comment
    }))
  const overall = overallEdited.value
    ? { comment: overallComment.value, expected: baseOverall.value }
    : null
  emit('save', items, overall)
}
</script>

<style scoped>
.rubric-form__empty {
  border: 1px dashed var(--border-light);
  border-radius: 8px;
  padding: 1.5rem;
  font-size: 0.9rem;
  color: var(--text-muted);
}

.rubric-form {
  display: flex;
  flex-direction: column;
  gap: 0;
  max-width: 22rem;
}

/* Criteria read as one seamless panel: no gaps, no dividers between them.
   The one above's bottom padding is the space above each criterion, the
   same as the space below its name. */
.rubric-form__criterion + .rubric-form__criterion {
  border-top: none;
  border-top-left-radius: 0;
  border-top-right-radius: 0;
  padding-top: 0;
}

.rubric-form__criterion:has(+ .rubric-form__criterion) {
  border-bottom: none;
  border-bottom-left-radius: 0;
  border-bottom-right-radius: 0;
}

.rubric-form__criterion {
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 0.5rem 0.75rem;
  background: var(--surface-elevated);
}

.rubric-form__criterion-head {
  display: flow-root;
  margin-bottom: 0.5rem;
}

.rubric-form__name {
  font-weight: 400;
  font-size: 0.8rem;
  margin: 0;
}

.rubric-form__max {
  float: right;
  margin-left: 0.75rem;
  font-size: 0.8rem;
  color: var(--text-muted);
  white-space: nowrap;
}

.rubric-form__fields {
  display: grid;
  grid-template-columns: 2.75rem 1fr;
}

/* The mark and comment boxes join into one: square where they meet, sharing
   the border between them; the focused one's border shows over the other's. */
.rubric-form__fields .rubric-form__mark {
  border-top-right-radius: 0;
  border-bottom-right-radius: 0;
  /* Narrower sides, so "10.00" still fits the narrower box. */
  padding-left: 0.4rem;
  padding-right: 0.4rem;
}

.rubric-form__fields .rubric-form__comment {
  margin-left: -1px;
  border-top-left-radius: 0;
  border-bottom-left-radius: 0;
}

.rubric-form__fields .rubric-form__mark:focus,
.rubric-form__fields .rubric-form__comment:focus {
  position: relative;
  z-index: 1;
}

@media (max-width: 640px) {
  .rubric-form__fields {
    grid-template-columns: 1fr;
    gap: 0.5rem;
  }

  .rubric-form__fields .rubric-form__mark,
  .rubric-form__fields .rubric-form__comment {
    margin-left: 0;
    border-radius: 6px;
  }
}

.rubric-form__mark,
.rubric-form__comment {
  border: 1px solid var(--border-light);
  border-radius: 6px;
  padding: 0.45rem 0.6rem;
  font-size: 0.85rem;
  font-family: inherit;
  background: var(--surface-elevated);
  color: var(--charcoal);
}

.rubric-form__mark:focus,
.rubric-form__comment:focus {
  outline: none;
  border-color: var(--dark-green);
}

/* Hide the native number spinners — marks are typed, not stepped. */
.rubric-form__mark {
  appearance: textfield;
  -moz-appearance: textfield;
}

.rubric-form__mark::-webkit-inner-spin-button,
.rubric-form__mark::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.rubric-form__comment {
  resize: vertical;
}

.rubric-form__overall-input {
  width: 100%;
  margin-top: 0.5rem;
}

.rubric-form__actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 1rem;
}
</style>
