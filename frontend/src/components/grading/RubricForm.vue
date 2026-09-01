<template>
  <div v-if="submission">
    <div v-if="criteria.length === 0 && !overallCommentLabel" class="rubric-form__empty">
      No rubric defined for this component yet. Add criteria in the Django admin
      rubric editor, then reload.
    </div>

    <form v-else class="rubric-form" @submit.prevent="handleSubmit">
      <div v-for="c in criteria" :key="c.id" class="rubric-form__criterion">
        <div class="rubric-form__criterion-head">
          <div>
            <p class="rubric-form__name">{{ c.name }}</p>
            <p v-if="c.description" class="rubric-form__description">{{ c.description }}</p>
          </div>
          <span class="rubric-form__max">/ {{ c.max_mark }}</span>
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
            @input="setMark(c.id, ($event.target as HTMLInputElement).value)"
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
        <button type="submit" class="btn btn-primary btn-sm" :disabled="isSaving">
          {{ isSaving ? 'Saving…' : criteria.length === 0 ? 'Save Comment' : 'Save marks' }}
        </button>
      </div>
    </form>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate } from 'vue-router'
import type { Grade, GradeBulkItem, RubricCriterion, Submission } from '@/utils/gradingAPI'

const props = defineProps<{
  submission: Submission | null
  criteria: RubricCriterion[]
  grades: Grade[]
  isSaving: boolean
  /** Heading for the overall-comment box; omit/null to hide it (e.g. SAQ). */
  overallCommentLabel?: string | null
}>()

const emit = defineEmits<{
  /** overallComment is null when the box is hidden for this component. */
  save: [items: GradeBulkItem[], overallComment: string | null]
}>()

type FormRow = { mark: string; comment: string }

const state = reactive<Record<number, FormRow>>({})
const overallComment = ref('')

// Mirror the server's overall comment whenever the submission (re)loads.
watch(
  () => props.submission,
  (submission) => {
    overallComment.value = submission?.overall_comment ?? ''
  },
  { immediate: true }
)

// Preload form state from existing grades keyed by criterion id, with empty
// defaults for un-graded criteria. Re-runs when the payload refetches after a
// save round-trip so the form always mirrors the server.
watch(
  () => [props.criteria, props.grades] as const,
  ([criteria, grades]) => {
    const byCriterion = new Map<number, Grade>()
    for (const g of grades) byCriterion.set(g.criterion, g)
    for (const key of Object.keys(state)) delete state[Number(key)]
    for (const c of criteria) {
      const g = byCriterion.get(c.id)
      state[c.id] = { mark: g?.mark ?? '', comment: g?.comment ?? '' }
    }
  },
  { immediate: true }
)

// Unsaved edits: any mark, comment, or overall comment differing from the
// last server payload. Retyping the exact stored value counts as clean.
const isDirty = computed(() => {
  const byCriterion = new Map<number, Grade>()
  for (const g of props.grades) byCriterion.set(g.criterion, g)
  const rowsDirty = props.criteria.some((c) => {
    const row = state[c.id]
    if (!row) return false
    const g = byCriterion.get(c.id)
    return row.mark.trim() !== (g?.mark ?? '').trim() || row.comment !== (g?.comment ?? '')
  })
  const overallDirty = props.overallCommentLabel
    ? overallComment.value !== (props.submission?.overall_comment ?? '')
    : false
  return rowsDirty || overallDirty
})

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

const setComment = (criterionId: number, comment: string) => {
  if (state[criterionId]) state[criterionId].comment = comment
}

const handleSubmit = () => {
  if (!props.submission) return
  const items: GradeBulkItem[] = props.criteria.map((c) => ({
    submission: props.submission!.id,
    criterion: c.id,
    // Empty string -> null so the mark is stored as "not graded yet" rather
    // than 0. Numeric validation is loose here — DRF's DecimalField rejects
    // anything unparseable and the error surfaces to the caller.
    mark: state[c.id]?.mark?.trim() ? state[c.id].mark : null,
    comment: state[c.id]?.comment ?? ''
  }))
  emit('save', items, props.overallCommentLabel ? overallComment.value : null)
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

/* Criteria read as one seamless panel: no gaps, no dividers between them. */
.rubric-form__criterion + .rubric-form__criterion {
  border-top: none;
  border-top-left-radius: 0;
  border-top-right-radius: 0;
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
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}

.rubric-form__name {
  font-weight: 400;
  font-size: 0.85rem;
  margin: 0;
}

.rubric-form__description {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin: 0;
}

.rubric-form__max {
  font-size: 0.8rem;
  color: var(--text-muted);
  white-space: nowrap;
}

.rubric-form__fields {
  display: grid;
  grid-template-columns: 3.5rem 1fr;
  gap: 0.5rem;
}

@media (max-width: 640px) {
  .rubric-form__fields {
    grid-template-columns: 1fr;
  }
}

.rubric-form__mark,
.rubric-form__comment {
  border: 1px solid var(--border-light);
  border-radius: 6px;
  padding: 0.45rem 0.6rem;
  font-size: 0.9rem;
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
