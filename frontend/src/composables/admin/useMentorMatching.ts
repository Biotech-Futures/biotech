import { computed, ref } from 'vue'
import {
  type MentorListItem,
  type MentorMatchMode,
  confirmMentorAssignments,
  fetchMentorMatchMentorList,
  fetchMentorMatchRecommendations
} from '@/utils/adminAPI'
import { logApiError } from '@/utils/apiError'
import {
  type MentorGroupRecommendation,
  parseMentorRecommendations
} from '@/utils/adminMatching'

export type {
  MentorGroupRecommendation,
  MentorMatchGroup,
  MentorScoreBreakdown,
  RecommendedMentor
} from '@/utils/adminMatching'

/** Copy for the mode selector — wording taken from the reference app. */
export const MENTOR_MATCH_MODES: { value: MentorMatchMode; label: string; description: string }[] = [
  {
    value: 'balanced',
    label: 'Balanced',
    description:
      'Considers all available mentors for every group. Same-country mentors are preferred, but cross-country mentors can fill in when needed. Best overall coverage.'
  },
  {
    value: 'strict',
    label: 'Strict',
    description:
      'Only matches groups with mentors from the same country (or GLOBAL mentors). Groups with no compatible mentor in their country will be left unmatched.'
  },
  {
    value: 'coverage',
    label: 'Coverage',
    description:
      'Two-phase matching: first assigns same-country mentors, then uses remaining mentor capacity to cover still-unmatched groups across other countries. Maximises the number of matched groups.'
  }
]

export function useMentorMatching() {
  const loading = ref(false)
  const confirming = ref(false)
  const error = ref('')
  const hasRun = ref(false)

  const mode = ref<MentorMatchMode>('balanced')
  const recommendations = ref<MentorGroupRecommendation[]>([])
  const mentors = ref<MentorListItem[]>([])

  /** Mentors with no remaining capacity are hidden unless this is on. */
  const showFullMentors = ref(false)
  /** Groups the admin has ticked for confirmation, keyed by groupId. */
  const selectedGroupIds = ref<Set<number>>(new Set())

  // -- Derived ----------------------------------------------------------------

  const modeDescription = computed(
    () => MENTOR_MATCH_MODES.find((entry) => entry.value === mode.value)?.description ?? ''
  )

  const availableMentors = computed(() =>
    mentors.value.filter((mentor) => showFullMentors.value || mentor.remainingCapacity > 0)
  )

  /** Recommendations the matcher could not place — no mentor was compatible. */
  const unmatchedRecommendations = computed(() =>
    recommendations.value.filter((entry) => entry.recommendedMentor === null)
  )

  const matchableRecommendations = computed(() =>
    recommendations.value.filter((entry) => entry.recommendedMentor !== null)
  )

  /**
   * Total remaining mentor capacity against the number of groups still needing
   * one. A shortage means no mode can cover everything — worth surfacing rather
   * than letting the admin re-run repeatedly expecting a different result.
   */
  const capacityShortage = computed(() => {
    const totalCapacity = mentors.value.reduce(
      (sum, mentor) => sum + mentor.remainingCapacity,
      0
    )
    const shortage = unmatchedRecommendations.value.length - totalCapacity
    return shortage > 0 ? { totalCapacity, shortage } : null
  })

  const selectedCount = computed(() => selectedGroupIds.value.size)

  const allSelected = computed(
    () =>
      matchableRecommendations.value.length > 0 &&
      matchableRecommendations.value.every((entry) =>
        selectedGroupIds.value.has(entry.group.groupId)
      )
  )

  // -- Selection --------------------------------------------------------------

  const toggleOne = (groupId: number) => {
    const next = new Set(selectedGroupIds.value)
    if (next.has(groupId)) next.delete(groupId)
    else next.add(groupId)
    selectedGroupIds.value = next
  }

  const toggleAll = () => {
    if (allSelected.value) {
      selectedGroupIds.value = new Set()
      return
    }
    selectedGroupIds.value = new Set(
      matchableRecommendations.value.map((entry) => entry.group.groupId)
    )
  }

  const clearSelection = () => {
    selectedGroupIds.value = new Set()
  }

  // -- Actions ----------------------------------------------------------------

  /** The mentor pool is supporting data; a failure here must not blank the board. */
  const loadMentors = async () => {
    try {
      mentors.value = await fetchMentorMatchMentorList()
    } catch (poolError) {
      logApiError('admin.matching.mentor.pool', poolError)
      mentors.value = []
    }
  }

  const run = async () => {
    loading.value = true
    error.value = ''
    try {
      const parsed = parseMentorRecommendations(
        await fetchMentorMatchRecommendations(mode.value)
      )
      if (!parsed.ok) {
        error.value = parsed.message
        recommendations.value = []
        selectedGroupIds.value = new Set()
        return
      }
      recommendations.value = parsed.data
      // Deliberately left empty: confirming writes live mentor assignments, and
      // `coverage` mode intentionally produces weaker cross-country matches, so
      // the admin opts in per row rather than unticking a pre-filled board.
      // Matches the reference app ("Confirm Selected (n)", disabled at zero).
      selectedGroupIds.value = new Set()
      hasRun.value = true
      await loadMentors()
    } catch (runError) {
      logApiError('admin.matching.mentor.run', runError)
      error.value =
        runError instanceof Error ? runError.message : 'Unable to run mentor matching.'
      recommendations.value = []
      selectedGroupIds.value = new Set()
    } finally {
      loading.value = false
    }
  }

  const setMode = (next: MentorMatchMode) => {
    if (mode.value === next) return
    mode.value = next
    // Results are mode-specific, so a stale board would misrepresent the choice.
    recommendations.value = []
    selectedGroupIds.value = new Set()
    hasRun.value = false
  }

  const confirm = async (): Promise<boolean> => {
    if (confirming.value) return false

    const payload = matchableRecommendations.value
      .filter((entry) => selectedGroupIds.value.has(entry.group.groupId))
      .map((entry) => ({
        groupId: entry.group.groupId,
        mentorUserId: entry.recommendedMentor!.mentorId
      }))

    if (payload.length === 0) {
      error.value = 'Select at least one recommendation to confirm.'
      return false
    }

    confirming.value = true
    error.value = ''
    try {
      await confirmMentorAssignments(payload)
      await run()
      return true
    } catch (confirmError) {
      logApiError('admin.matching.mentor.confirm', confirmError)
      error.value =
        confirmError instanceof Error
          ? confirmError.message
          : 'Unable to confirm the mentor assignments.'
      return false
    } finally {
      confirming.value = false
    }
  }

  return {
    loading,
    confirming,
    error,
    hasRun,
    mode,
    modeDescription,
    recommendations,
    matchableRecommendations,
    unmatchedRecommendations,
    mentors,
    availableMentors,
    showFullMentors,
    capacityShortage,
    selectedGroupIds,
    selectedCount,
    allSelected,
    toggleOne,
    toggleAll,
    clearSelection,
    run,
    setMode,
    confirm
  }
}
