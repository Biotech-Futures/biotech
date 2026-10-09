import { computed, ref } from 'vue'
import {
  type MentorListItem,
  type MentorMatchMode,
  confirmMentorAssignments,
  fetchMentorMatchMentorList,
  fetchMentorMatchRecommendations,
  fetchUnmatchedGroups
} from '@/utils/adminAPI'
import { logApiError } from '@/utils/apiError'
import {
  type MentorGroupRecommendation,
  type MentorMatchGroup,
  parseMentorRecommendations,
  parseUnmatchedGroups
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

export type RecommendationSortKey =
  | 'group'
  | 'country'
  | 'students'
  | 'mentor'
  | 'institution'
  | 'capacity'
  | 'score'

export function useMentorMatching() {
  const loading = ref(false)
  /** Initial load of the two reference lists, before any match is run. */
  const loadingLists = ref(true)
  const confirming = ref(false)
  const error = ref('')
  const hasRun = ref(false)

  const mode = ref<MentorMatchMode>('balanced')
  const recommendations = ref<MentorGroupRecommendation[]>([])
  const mentors = ref<MentorListItem[]>([])
  /** Groups still needing a mentor — shown before and after a run. */
  const unmatchedGroups = ref<MentorMatchGroup[]>([])
  const expandedGroupIds = ref<Set<number>>(new Set())
  const expandedMentorIds = ref<Set<number>>(new Set())

  // -- Recommendations table --------------------------------------------------

  const recSearch = ref('')
  const recCountry = ref('all')
  const expandedRecIds = ref<Set<number>>(new Set())
  const recSort = ref<{ key: RecommendationSortKey; direction: 'asc' | 'desc' }>({
    key: 'score',
    direction: 'desc'
  })

  /**
   * groupId -> mentorId the admin picked instead of the recommended one.
   * Held locally: nothing reaches the server until confirm, so a "Change" is
   * an edit to the proposal rather than a replace against live data.
   */
  const mentorOverrides = ref<Map<number, number>>(new Map())

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

  const availableMentorCount = computed(
    () => mentors.value.filter((mentor) => mentor.remainingCapacity > 0).length
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

  // -- Recommendations: overrides, filtering, sorting -------------------------

  /** The mentor this row would actually assign — the override, or the pick. */
  const effectiveMentorFor = (entry: MentorGroupRecommendation) => {
    const overrideId = mentorOverrides.value.get(entry.group.groupId)
    if (overrideId === undefined) return entry.recommendedMentor
    const mentor = mentors.value.find((candidate) => candidate.mentorId === overrideId)
    if (!mentor) return entry.recommendedMentor
    return {
      mentorId: mentor.mentorId,
      name: mentor.name,
      countryName: mentor.countryName,
      institution: mentor.institution,
      interests: mentor.interests,
      remainingCapacity: mentor.remainingCapacity
    }
  }

  const isOverridden = (groupId: number) => mentorOverrides.value.has(groupId)

  const setMentorOverride = (groupId: number, mentorId: number | null) => {
    const next = new Map(mentorOverrides.value)
    if (mentorId === null) next.delete(groupId)
    else next.set(groupId, mentorId)
    mentorOverrides.value = next
  }

  /** Countries present in the current recommendations, for the filter. */
  const recCountries = computed(() => {
    const seen = new Set<string>()
    for (const entry of recommendations.value) {
      if (entry.group.countryName) seen.add(entry.group.countryName)
    }
    return [...seen].sort((a, b) => a.localeCompare(b))
  })

  const filteredRecommendations = computed(() => {
    const term = recSearch.value.trim().toLowerCase()
    return recommendations.value.filter((entry) => {
      if (recCountry.value !== 'all' && entry.group.countryName !== recCountry.value) {
        return false
      }
      if (!term) return true
      const mentor = effectiveMentorFor(entry)
      const haystack = [
        entry.group.groupName,
        entry.group.countryName ?? '',
        mentor?.name ?? '',
        mentor?.institution ?? ''
      ]
        .join(' ')
        .toLowerCase()
      return haystack.includes(term)
    })
  })

  const sortValue = (entry: MentorGroupRecommendation, key: RecommendationSortKey) => {
    const mentor = effectiveMentorFor(entry)
    switch (key) {
      case 'group':
        return entry.group.groupName
      case 'country':
        return entry.group.countryName ?? ''
      case 'students':
        return entry.group.studentCount
      case 'mentor':
        return mentor?.name ?? ''
      case 'institution':
        return mentor?.institution ?? ''
      case 'capacity':
        return mentor?.remainingCapacity ?? -1
      case 'score':
        return entry.score
    }
  }

  const sortedRecommendations = computed(() => {
    const { key, direction } = recSort.value
    const factor = direction === 'asc' ? 1 : -1
    return [...filteredRecommendations.value].sort((a, b) => {
      const left = sortValue(a, key)
      const right = sortValue(b, key)
      if (typeof left === 'number' && typeof right === 'number') {
        return (left - right) * factor
      }
      return String(left).localeCompare(String(right)) * factor
    })
  })

  const setRecSort = (key: RecommendationSortKey) => {
    recSort.value =
      recSort.value.key === key
        ? { key, direction: recSort.value.direction === 'asc' ? 'desc' : 'asc' }
        : { key, direction: 'asc' }
  }

  const recSortIcon = (key: RecommendationSortKey) => {
    if (recSort.value.key !== key) return 'fa-sort'
    return recSort.value.direction === 'asc' ? 'fa-sort-up' : 'fa-sort-down'
  }

  const toggleRecExpanded = (groupId: number) => {
    const next = new Set(expandedRecIds.value)
    if (next.has(groupId)) next.delete(groupId)
    else next.add(groupId)
    expandedRecIds.value = next
  }

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

  const loadUnmatchedGroups = async () => {
    try {
      const parsed = parseUnmatchedGroups(await fetchUnmatchedGroups())
      unmatchedGroups.value = parsed.ok ? parsed.data : []
      if (!parsed.ok) logApiError('admin.matching.mentor.groups', new Error(parsed.message))
    } catch (groupsError) {
      logApiError('admin.matching.mentor.groups', groupsError)
      unmatchedGroups.value = []
    }
  }

  /** Both reference lists, shown before any match has been run. */
  const loadLists = async () => {
    loadingLists.value = true
    try {
      await Promise.all([loadMentors(), loadUnmatchedGroups()])
    } finally {
      loadingLists.value = false
    }
  }

  const toggleGroupExpanded = (groupId: number) => {
    const next = new Set(expandedGroupIds.value)
    if (next.has(groupId)) next.delete(groupId)
    else next.add(groupId)
    expandedGroupIds.value = next
  }

  const toggleMentorExpanded = (mentorId: number) => {
    const next = new Set(expandedMentorIds.value)
    if (next.has(mentorId)) next.delete(mentorId)
    else next.add(mentorId)
    expandedMentorIds.value = next
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
      // A fresh proposal supersedes any manual mentor swaps from the last one.
      mentorOverrides.value = new Map()
      expandedRecIds.value = new Set()
      hasRun.value = true
      // Capacity changes as assignments are confirmed, and the unmatched list
      // shrinks, so both are refreshed alongside a run.
      await Promise.all([loadMentors(), loadUnmatchedGroups()])
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

    const payload = recommendations.value
      .filter((entry) => selectedGroupIds.value.has(entry.group.groupId))
      .map((entry) => ({ groupId: entry.group.groupId, mentor: effectiveMentorFor(entry) }))
      // A row whose mentor was cleared has nothing to assign.
      .filter((entry): entry is { groupId: number; mentor: NonNullable<typeof entry.mentor> } =>
        entry.mentor !== null
      )
      .map((entry) => ({ groupId: entry.groupId, mentorUserId: entry.mentor.mentorId }))

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
    loadingLists,
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
    availableMentorCount,
    unmatchedGroups,
    expandedGroupIds,
    expandedMentorIds,
    showFullMentors,
    capacityShortage,
    selectedGroupIds,
    selectedCount,
    allSelected,
    toggleOne,
    toggleAll,
    clearSelection,
    toggleGroupExpanded,
    toggleMentorExpanded,
    recSearch,
    recCountry,
    recCountries,
    recSort,
    setRecSort,
    recSortIcon,
    sortedRecommendations,
    expandedRecIds,
    toggleRecExpanded,
    effectiveMentorFor,
    isOverridden,
    setMentorOverride,
    loadLists,
    run,
    setMode,
    confirm
  }
}
