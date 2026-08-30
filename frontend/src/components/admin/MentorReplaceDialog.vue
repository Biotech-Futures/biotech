<template>
  <FormSheet
    :model-value="open"
    title="Replace Inactive Mentors"
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
            Current: <span class="replace-dialog__danger">{{ group.mentor.name }} (inactive)</span>
          </p>
          <p v-if="topSuggestionFor(group.groupId)" class="replace-dialog__suggested">
            ★ Suggested: {{ topName(group.groupId) }} (score {{ topScore(group.groupId) }})
          </p>
          <p v-else-if="suggestionsFor(group.groupId).length > 0" class="replace-dialog__hint">
            Every suggested mentor is at capacity — you can still pick one manually below.
          </p>
        </div>
        <select
          v-model="selections[group.groupId]"
          class="form-input replace-dialog__select"
          :disabled="busy"
          :aria-label="`Replacement mentor for ${group.groupName}`"
        >
          <option value="">Select action</option>
          <option :value="UNASSIGN_VALUE">— Unassign (leave unmatched)</option>
          <option v-for="option in optionsFor(group.groupId)" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </div>
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
import FormSheet from '@/components/admin/FormSheet.vue'
import {
  type MatchedGroup,
  type MentorListItem,
  type MentorReplaceSuggestion,
  confirmMentorAssignments,
  fetchMentorReplaceSuggestions,
  unassignMentors
} from '@/utils/adminAPI'
import { logApiError } from '@/utils/apiError'

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
  return `${count} group${count === 1 ? '' : 's'} ${count === 1 ? 'has' : 'have'} an inactive mentor. The best match from the matcher is pre-selected — adjust any, or choose "Unassign" to leave a group unmatched.`
})

const suggestionsFor = (groupId: number): MentorReplaceSuggestion[] =>
  suggestionsByGroup.value.get(groupId) ?? []

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
    options.push({
      value: String(mentor.mentorId),
      label: `${mentor.name}${mentor.remainingCapacity === 0 ? ' (full)' : ''}`
    })
  }
  return options
}

const actionCount = computed(
  () => props.inactiveGroups.filter((group) => selections[group.groupId]).length
)

const applyDefaults = () => {
  for (const group of props.inactiveGroups) {
    if (selections[group.groupId] !== undefined) continue
    const top = (suggestionsByGroup.value.get(group.groupId) ?? []).find(
      (s) => !s.atCapacity
    )
    if (top) selections[group.groupId] = String(top.mentorUserId)
  }
}

const loadSuggestions = async () => {
  loadingSuggestions.value = true
  error.value = ''
  try {
    const results = await Promise.all(
      props.inactiveGroups.map((group) => fetchMentorReplaceSuggestions(group.groupId))
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
        ? confirmMentorAssignments(assignments).then((result) => result.confirmedCount)
        : Promise.resolve(0),
      unassigns.length ? unassignMentors(unassigns).then((result) => result.unassignedCount) : Promise.resolve(0)
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
  color: var(--charcoal);
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
</style>