import { computed, ref } from 'vue'
import { confirmStudentAssignments, fetchStudentMatch } from '@/utils/adminAPI'
import { logApiError } from '@/utils/apiError'
import {
  type MatchGroupId,
  type MatchStudent,
  type MatchTutor,
  type RecommendedStudent,
  type StudentMatchData,
  parseStudentMatchData,
  toConfirmGroupId
} from '@/utils/adminMatching'

/** A group rendered as a drop target, merged from notFullGroups + recommendations. */
export interface BoardGroup {
  /** Integer for existing groups, `new-*` for ones the matcher proposes forming. */
  id: MatchGroupId
  groupName: string
  maxSize: number
  tutor: MatchTutor
  existingStudents: MatchStudent[]
  sharedInterests: string[]
}

export type GroupFilter = 'all' | 'needs_action' | 'has_space' | 'full'

export const GROUP_FILTERS: { value: GroupFilter; label: string }[] = [
  { value: 'all', label: 'All groups' },
  { value: 'needs_action', label: 'Has recommended students' },
  { value: 'has_space', label: 'Has space' },
  { value: 'full', label: 'Full groups' }
]

const DEFAULT_MAX_SIZE = 5

const emptyData = (): StudentMatchData => ({
  recommendations: [],
  unmatchedStudents: [],
  notFullGroups: []
})

/** Interests common to every existing member — what the group is "about". */
const sharedInterestsOf = (students: MatchStudent[]): string[] => {
  if (students.length === 0) return []
  const [first, ...rest] = students
  return first.interests.filter((interest) =>
    rest.every((student) => student.interests.includes(interest))
  )
}

/**
 * State and behaviour for the Student Matching board.
 *
 * The matcher is never run on mount — it is a deliberate admin action and its
 * output is only a proposal until `confirm()` writes it. Students the admin
 * drags live in `buckets` (per group) and `waiting`; students already in a
 * group are fixed and never move.
 */
export function useStudentMatching() {
  const loading = ref(false)
  const confirming = ref(false)
  const error = ref('')
  /** False until the first run, so an unrun board never reads as "all matched". */
  const hasRun = ref(false)

  const data = ref<StudentMatchData>(emptyData())
  const groups = ref<BoardGroup[]>([])

  /** groupId -> students proposed or dragged into it. Mutated by drag and drop. */
  const buckets = ref<Record<string, RecommendedStudent[]>>({})
  /** Students held out of every group. */
  const waiting = ref<RecommendedStudent[]>([])

  /**
   * studentId -> the group the matcher originally proposed for them.
   *
   * A student's score is only meaningful for that pairing — it bakes in the
   * group's country, timezone spread and size. Once dragged elsewhere the
   * number is stale, so the board needs to know where it came from rather than
   * presenting it as the fit for wherever the student now sits.
   */
  const recommendedGroup = ref<Map<string, { id: MatchGroupId; groupName: string }>>(new Map())

  const search = ref('')
  const groupFilter = ref<GroupFilter>('all')

  // -- Board construction -----------------------------------------------------

  const seedBoard = (source: StudentMatchData) => {
    // Keyed by String(id) so integer and `new-*` ids share one namespace.
    const byId = new Map<string, BoardGroup>()
    const nextBuckets: Record<string, RecommendedStudent[]> = {}
    const nextRecommended = new Map<string, { id: MatchGroupId; groupName: string }>()

    // Not-full groups first: they render as empty drop targets even when the
    // matcher proposed nobody for them.
    for (const group of source.notFullGroups) {
      byId.set(String(group.id), {
        id: group.id,
        groupName: group.groupName,
        maxSize: group.maxSize ?? DEFAULT_MAX_SIZE,
        tutor: group.tutor,
        existingStudents: group.existingStudents,
        sharedInterests: sharedInterestsOf(group.existingStudents)
      })
      nextBuckets[String(group.id)] = []
    }

    for (const group of source.recommendations) {
      if (!byId.has(String(group.id))) {
        byId.set(String(group.id), {
          id: group.id,
          groupName: group.groupName,
          maxSize: group.maxSize ?? DEFAULT_MAX_SIZE,
          tutor: group.tutor,
          existingStudents: group.existingStudents,
          sharedInterests: sharedInterestsOf(group.existingStudents)
        })
      }

      const existingIds = new Set(group.existingStudents.map((student) => student.id))
      const proposed = group.recommendStudents.filter(
        (entry) => !existingIds.has(entry.student.id)
      )
      nextBuckets[String(group.id)] = proposed

      for (const entry of proposed) {
        nextRecommended.set(String(entry.student.id), {
          id: group.id,
          groupName: group.groupName
        })
      }
    }

    groups.value = [...byId.values()]
    buckets.value = nextBuckets
    waiting.value = [...source.unmatchedStudents]
    recommendedGroup.value = nextRecommended
  }

  /** The group the matcher proposed for this student, if any. */
  const recommendedGroupOf = (studentId: string | number) =>
    recommendedGroup.value.get(String(studentId)) ?? null

  /** True when the student is sitting where the matcher put them. */
  const isInRecommendedGroup = (studentId: string | number, groupId: MatchGroupId) =>
    String(recommendedGroupOf(studentId)?.id) === String(groupId)

  // -- Derived ----------------------------------------------------------------

  const bucketFor = (groupId: MatchGroupId): RecommendedStudent[] =>
    buckets.value[String(groupId)] ?? []

  const seatsUsed = (group: BoardGroup) =>
    group.existingStudents.length + bucketFor(group.id).length

  const openSeatsFor = (group: BoardGroup) => Math.max(0, group.maxSize - seatsUsed(group))

  const visibleGroups = computed(() => {
    const term = search.value.trim().toLowerCase()
    return groups.value.filter((group) => {
      if (term) {
        const haystack = `${group.groupName} ${group.tutor?.name ?? ''}`.toLowerCase()
        if (!haystack.includes(term)) return false
      }
      switch (groupFilter.value) {
        case 'needs_action':
          return bucketFor(group.id).length > 0
        case 'has_space':
          return openSeatsFor(group) > 0
        case 'full':
          return openSeatsFor(group) === 0
        default:
          return true
      }
    })
  })

  const totalGroups = computed(() => groups.value.length)
  const visibleGroupCount = computed(() => visibleGroups.value.length)
  const totalOpenSeats = computed(() =>
    groups.value.reduce((sum, group) => sum + openSeatsFor(group), 0)
  )
  const waitingCount = computed(() => waiting.value.length)

  /** Students sitting in a group bucket — i.e. what confirm would write. */
  const assignmentCount = computed(() =>
    Object.values(buckets.value).reduce((sum, bucket) => sum + bucket.length, 0)
  )

  const isEmpty = computed(() => groups.value.length === 0 && waiting.value.length === 0)

  // -- Actions ----------------------------------------------------------------

  const run = async () => {
    loading.value = true
    error.value = ''
    try {
      const parsed = parseStudentMatchData(await fetchStudentMatch())
      if (!parsed.ok) {
        // Surface the shape mismatch rather than rendering coerced defaults —
        // these assignments get written straight to production on confirm.
        error.value = parsed.message
        data.value = emptyData()
        seedBoard(emptyData())
        return
      }
      data.value = parsed.data
      seedBoard(parsed.data)
      hasRun.value = true
    } catch (runError) {
      logApiError('admin.matching.student.run', runError)
      error.value =
        runError instanceof Error ? runError.message : 'Unable to run student matching.'
      data.value = emptyData()
      seedBoard(emptyData())
    } finally {
      loading.value = false
    }
  }

  /** Restore the algorithm's original proposal, discarding manual moves. */
  const reset = () => {
    seedBoard(data.value)
    error.value = ''
  }

  const confirm = async (): Promise<boolean> => {
    if (confirming.value) return false

    const payload = Object.entries(buckets.value)
      .flatMap(([groupId, bucket]) =>
        bucket.map((entry) => ({
          studentId: Number(entry.student.id),
          // Bucket keys are strings, so a `new-*` id has to be handed back
          // verbatim rather than coerced — the backend creates the real group
          // from it on confirm.
          groupId: toConfirmGroupId(groupId)
        }))
      )
      // `> 0`, not Number.isFinite: Number('') is 0, which is finite, so a
      // missing id would otherwise be posted as student 0. toConfirmGroupId
      // returns null for a group id that is neither `new-*` nor a usable
      // integer, which drops it here for the same reason.
      .filter(
        (entry): entry is { studentId: number; groupId: string | number } =>
          entry.studentId > 0 && entry.groupId !== null
      )

    if (payload.length === 0) {
      error.value = 'No assignments to confirm.'
      return false
    }

    confirming.value = true
    error.value = ''
    try {
      await confirmStudentAssignments(payload)
      // Re-run so the board reflects what is now actually in the database.
      await run()
      return true
    } catch (confirmError) {
      logApiError('admin.matching.student.confirm', confirmError)
      error.value =
        confirmError instanceof Error
          ? confirmError.message
          : 'Unable to confirm the assignments.'
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
    groups,
    buckets,
    waiting,
    search,
    groupFilter,
    visibleGroups,
    totalGroups,
    visibleGroupCount,
    totalOpenSeats,
    waitingCount,
    assignmentCount,
    isEmpty,
    bucketFor,
    seatsUsed,
    openSeatsFor,
    recommendedGroupOf,
    isInRecommendedGroup,
    run,
    reset,
    confirm
  }
}
