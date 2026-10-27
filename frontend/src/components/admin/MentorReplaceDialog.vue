<template>
  <FormSheet
    :model-value="open"
    title="Replace Idle Mentors"
    :description="description"
    width="min(100vw, 600px)"
    @update:model-value="onDismiss"
    @close="onDismiss"
  >
    <p v-if="error" class="replace-dialog__error" role="alert">{{ error }}</p>

    <p v-if="loadingSuggestions" class="replace-dialog__hint">
      <span class="replace-dialog__spinner" aria-hidden="true"></span>
      Scoring mentors…
    </p>

    <div v-else class="replace-dialog__list">
      <div v-for="group in inactiveGroups" :key="group.groupId" class="replace-dialog__row">
        <div class="replace-dialog__group">
          <p class="replace-dialog__name">{{ group.groupName }}</p>
          <p class="replace-dialog__current">
            Current:
            <span class="replace-dialog__danger">
              {{ group.mentor.name }}
              ({{ mentorConcern(group.mentor, idleDays) === 'idle' ? 'idle' : 'inactive' }})
            </span>
          </p>
          <p v-if="topSuggestionFor(group.groupId)" class="replace-dialog__suggested">
            ★ Suggested: {{ topName(group.groupId) }} (score {{ topScore(group.groupId) }})
          </p>
          <p v-else-if="suggestionsFor(group.groupId).length > 0" class="replace-dialog__hint">
            Every suggested mentor is at capacity - you can still pick one manually below.
          </p>
        </div>
        <AppSelect
          v-model="selections[group.groupId]"
          class="form-input replace-dialog__select"
          :options="actionOptionsFor(group.groupId)"
          placeholder="Select action"
          searchable
          :disabled="busy"
          :aria-label="`Replacement mentor for ${group.groupName}`"
        />
      </div>
    </div>

    <!-- One pair for the batch: the admin is confirming a single action over
         several groups, so per-row toggles would be noise. -->
    <div class="replace-dialog__notify">
      <label>
        <input v-model="notifyDeparting" type="checkbox" :disabled="busy" />
        Notify departing mentors
      </label>
      <label>
        <input v-model="notifyIncoming" type="checkbox" :disabled="busy" />
        Notify incoming mentors
      </label>
    </div>

    <template #footer>
      <button type="button" class="btn btn-outline" :disabled="busy" @click="onDismiss">
        Cancel
      </button>
      <button
        type="button"
        class="btn btn-primary"
        :disabled="busy || actionCount === 0"
        @click="confirm"
      >
        {{ busy ? 'Confirming...' : `Confirm${actionCount > 0 ? ` (${actionCount})` : ''}` }}
      </button>
    </template>
  </FormSheet>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import AppSelect, { type AppSelectOption } from '@/components/AppSelect.vue'
import FormSheet from '@/components/admin/FormSheet.vue'
import {
  type MatchedGroup,
  type MentorListItem,
  type MentorReplaceSuggestion,
  confirmMentorAssignments,
  fetchMentorReplaceSuggestions,
  unassignMentors
} from '@/utils/adminAPI'
import { mentorConcern } from '@/utils/mentorFormat'
import { useIdleThreshold } from '@/composables/admin/useIdleThreshold'
import { logApiError } from '@/utils/apiError'

// The reason shown per row follows the threshold the admin set, like the
// counts on the screens behind this dialog.
const { idleDays } = useIdleThreshold()

const UNASSIGN_VALUE = '__unassign__'

const props = defineProps<{
  open: boolean
  inactiveGroups: MatchedGroup[]
  mentors: MentorListItem[]
}>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'confirmed'): void
}>()

const loadingSuggestions = ref(false)
const busy = ref(false)
const error = ref('')
const suggestionsByGroup = ref<Map<number, MentorReplaceSuggestion[]>>(new Map())
const selections = reactive<Record<number, string>>({})

const description = computed(() => {
  const count = props.inactiveGroups.length
  // "needs a new mentor" covers both reasons without claiming either; each row
  // says which one applies.
  return `${count} group${count === 1 ? '' : 's'} ${count === 1 ? 'needs' : 'need'} a new mentor. The best match from the matcher is pre-selected - adjust any, or choose "Unassign" to leave a group unmatched.`
})

/** The whole roster by id, so a scored suggestion can be held to the same
 *  check as the badge on the row above it. */
const mentorById = computed(
  () => new Map(props.mentors.map((mentor) => [mentor.mentorId, mentor]))
)

/**
 * Replacing an idle mentor with another idle one just moves the problem to a
 * new group, so nothing on this screen offers one.
 *
 * This has to be applied to the backend's scored suggestions as much as to the
 * raw pool. Matching is deliberately more forgiving - it forgives a recent
 * join date, which this screen does not - so it will score a mentor the row
 * beside it is flagging. Holding both to `mentorConcern`, against the same
 * threshold that paints the badge, is what stops the two disagreeing.
 */
const isOfferable = (mentorId: number): boolean => {
  const mentor = mentorById.value.get(mentorId)
  // The roster is every mentor, so a miss means a stale list rather than a
  // concern we failed to spot. Nothing to hold against them.
  return !mentor || mentorConcern(mentor, idleDays.value) === null
}

/** Filtered at the source: the "Suggested" line, the pre-selection and the
 *  dropdown all read from here, and they must not differ on who is eligible.
 *  Pre-selecting someone the dropdown refuses to list leaves a row stuck. */
const suggestionsFor = (groupId: number): MentorReplaceSuggestion[] =>
  (suggestionsByGroup.value.get(groupId) ?? []).filter((s) => isOfferable(s.mentorUserId))

const topSuggestionFor = (groupId: number): MentorReplaceSuggestion | undefined =>
  suggestionsFor(groupId).find((s) => !s.atCapacity) || suggestionsFor(groupId)[0]

const topName = (groupId: number) =>
  topSuggestionFor(groupId)?.name ?? ''

const topScore = (groupId: number) =>
  Math.round(topSuggestionFor(groupId)?.score ?? 0)

interface ReplaceOption {
  value: string
  label: string
}

/** Scored suggestions (already at capacity still listable, tagged "(full)") plus
 *  any unscored mentors who have a free seat. */
const optionsFor = (groupId: number): ReplaceOption[] => {
  const suggestions = suggestionsFor(groupId)
  const options = suggestions.map((s) => ({
    value: String(s.mentorUserId),
    label: `${s.name} · ${Math.round(s.score)}${s.atCapacity ? ' (full)' : ''}`
  }))
  const scoredIds = new Set(suggestions.map((s) => s.mentorUserId))
  for (const mentor of props.mentors) {
    if (scoredIds.has(mentor.mentorId)) continue
    if (mentor.remainingCapacity <= 0) continue
    if (!isOfferable(mentor.mentorId)) continue
    options.push({
      value: String(mentor.mentorId),
      label: `${mentor.name}${mentor.remainingCapacity === 0 ? ' (full)' : ''}`
    })
  }
  return options
}

/** Nothing yet, unassign, or one of the mentors. */
const actionOptionsFor = (groupId: number): AppSelectOption[] => [
  { value: '', label: 'Select action' },
  { value: UNASSIGN_VALUE, label: '— Unassign (leave unmatched)' },
  ...optionsFor(groupId)
]

const actionCount = computed(
  () => props.inactiveGroups.filter((group) => selections[group.groupId]).length
)

const notifyDeparting = ref(true)
const notifyIncoming = ref(true)

const applyDefaults = () => {
  for (const group of props.inactiveGroups) {
    if (selections[group.groupId] !== undefined) continue
    // Through `suggestionsFor`, so an ineligible mentor is never pre-selected.
    // Reading the raw map here meant a mentor the dropdown refused to list
    // could still be selected, invisibly - the row looked untouched and
    // Confirm sent them anyway. Still never someone already at capacity.
    const top = suggestionsFor(group.groupId).find((s) => !s.atCapacity)
    if (top) selections[group.groupId] = String(top.mentorUserId)
  }
}

const loadSuggestions = async () => {
  loadingSuggestions.value = true
  error.value = ''
  try {
    const results = await Promise.all(
      // The admin's own threshold decides who counts as idle, so it travels
      // with the request: a quiet mentor is not offered as a replacement.
      props.inactiveGroups.map((group) =>
        fetchMentorReplaceSuggestions(group.groupId, idleDays.value)
      )
    )
    const next = new Map<number, MentorReplaceSuggestion[]>()
    results.forEach((data) => next.set(data.groupId, data.suggestions))
    suggestionsByGroup.value = next
    applyDefaults()
  } catch (loadError) {
    logApiError('admin.mentors.replace-suggestions', loadError)
    error.value =
      loadError instanceof Error
        ? loadError.message
        : 'Replacement suggestions could not be loaded right now.'
    suggestionsByGroup.value = new Map()
  } finally {
    loadingSuggestions.value = false
  }
}

const reset = () => {
  for (const key of Object.keys(selections)) delete selections[Number(key)]
  suggestionsByGroup.value = new Map()
  error.value = ''
}

const onDismiss = () => {
  if (busy.value) return
  reset()
  emit('update:open', false)
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      reset()
      void loadSuggestions()
    }
  }
)

const confirm = async () => {
  if (busy.value) return
  const assignments: Array<{ groupId: number; mentorUserId: number }> = []
  const unassigns: number[] = []

  for (const group of props.inactiveGroups) {
    const value = selections[group.groupId]
    if (!value) continue
    if (value === UNASSIGN_VALUE) {
      unassigns.push(group.groupId)
    } else {
      assignments.push({ groupId: group.groupId, mentorUserId: Number(value) })
    }
  }

  if (!assignments.length && !unassigns.length) return

  busy.value = true
  error.value = ''
  try {
    await Promise.all([
      assignments.length
        ? confirmMentorAssignments(assignments, {
            idleDays: idleDays.value,
            notifyDeparting: notifyDeparting.value,
            notifyIncoming: notifyIncoming.value
          }).then((result) => result.confirmedCount)
        : Promise.resolve(0),
      // An unassigned group gains no mentor, so only the departing flag applies.
      unassigns.length
        ? unassignMentors(unassigns, { notifyDeparting: notifyDeparting.value }).then(
            (result) => result.unassignedCount
          )
        : Promise.resolve(0)
    ])
    reset()
    emit('update:open', false)
    emit('confirmed')
  } catch (submitError) {
    logApiError('admin.mentors.replace', submitError)
    error.value =
      submitError instanceof Error
        ? submitError.message
        : 'Bulk replace failed. Please try again.'
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.replace-dialog__error {
  margin: 0 0 1rem;
  padding: 0.7rem 0.9rem;
  border-left: 4px solid var(--danger);
  border-radius: 6px;
  background-color: rgba(220, 53, 69, 0.08);
  color: var(--danger);
  font-size: 0.875rem;
}

.replace-dialog__hint {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.replace-dialog__spinner {
  width: 16px;
  height: 16px;
  border: 2px solid var(--border-light);
  border-top-color: var(--dark-green);
  border-radius: 50%;
  animation: replace-dialog-spin 0.8s linear infinite;
}

.replace-dialog__list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.replace-dialog__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.85rem;
  border: 1px solid var(--border-light);
  border-radius: 10px;
  background-color: var(--bg-light);
}

.replace-dialog__group {
  min-width: 0;
}

.replace-dialog__name {
  margin: 0;
  font-weight: 600;
  color: var(--teal);
  overflow-wrap: anywhere;
}

.replace-dialog__current {
  margin: 0.15rem 0 0;
  font-size: 0.8rem;
  color: var(--text-muted);
}

.replace-dialog__danger {
  color: var(--danger);
}

.replace-dialog__suggested {
  margin: 0.15rem 0 0;
  font-size: 0.8rem;
  color: var(--dark-green);
}

.replace-dialog__select {
  flex-shrink: 0;
  width: 180px;
  font-size: 0.8rem;
}

@keyframes replace-dialog-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .replace-dialog__spinner {
    animation: none;
  }
}

.replace-dialog__notify {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  margin-top: 0.9rem;
  padding-top: 0.8rem;
  border-top: 1px solid var(--border-light);
  color: var(--text-muted);
  font-size: 0.82rem;
}

.replace-dialog__notify label {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}
</style>
