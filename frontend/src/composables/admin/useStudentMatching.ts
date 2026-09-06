import { computed, ref } from 'vue'
import { confirmStudentAssignments, fetchStudentMatch } from '@/utils/adminAPI'
import { logApiError } from '@/utils/apiError'
import {
  type MatchRecommendationGroup,
  type NotFullGroup,
  type RecommendedStudent,
  type StudentMatchData,
  parseStudentMatchData
} from '@/utils/adminMatching'

const emptyData = (): StudentMatchData => ({
  recommendations: [],
  unmatchedStudents: [],
  notFullGroups: []
})

/**
 * State and behaviour for the Student Matching tab.
 *
 * The matcher is never run on mount — it is a deliberate admin action, and the
 * results are only a proposal until `confirm()` writes them. `assignments`
 * therefore tracks a working copy seeded from the algorithm's output, which the
 * board may mutate (drag-to-assign) and `reset()` restores.
 */
export function useStudentMatching() {
  const loading = ref(false)
  const confirming = ref(false)
  const error = ref('')
  /** False until the first run, so the panel can show a call-to-action instead
   *  of an empty board that reads as "everything is matched". */
  const hasRun = ref(false)

  const data = ref<StudentMatchData>(emptyData())

  /** studentId -> groupId. The admin's working copy of the proposal. */
  const assignments = ref<Map<string, string | number>>(new Map())

  // -- Derived ----------------------------------------------------------------

  const recommendations = computed<MatchRecommendationGroup[]>(
    () => data.value.recommendations
  )
  const unmatchedStudents = computed<RecommendedStudent[]>(
    () => data.value.unmatchedStudents
  )
  const notFullGroups = computed<NotFullGroup[]>(() => data.value.notFullGroups)

  const recommendedCount = computed(() =>
    recommendations.value.reduce((total, group) => total + group.recommendStudents.length, 0)
  )

  const assignmentCount = computed(() => assignments.value.size)

  const isEmpty = computed(
    () =>
      recommendations.value.length === 0 &&
      unmatchedStudents.value.length === 0 &&
      notFullGroups.value.length === 0
  )

  /** Only students the algorithm placed — unmatched ones have no target group. */
  const seedAssignments = (source: StudentMatchData) => {
    const next = new Map<string, string | number>()
    for (const group of source.recommendations) {
      for (const entry of group.recommendStudents) {
        next.set(String(entry.student.id), group.id)
      }
    }
    assignments.value = next
  }

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
        assignments.value = new Map()
        return
      }
      data.value = parsed.data
      seedAssignments(parsed.data)
      hasRun.value = true
    } catch (runError) {
      logApiError('admin.matching.student.run', runError)
      error.value =
        runError instanceof Error ? runError.message : 'Unable to run student matching.'
      // Clear rather than keep a stale board — a half-loaded proposal is worse
      // than none, because confirming it would write the wrong assignments.
      data.value = emptyData()
      assignments.value = new Map()
    } finally {
      loading.value = false
    }
  }

  /** Restore the algorithm's original proposal, discarding manual changes. */
  const reset = () => {
    seedAssignments(data.value)
    error.value = ''
  }

  /** Move a student to a group, or drop them from the proposal with `null`. */
  const assignStudent = (studentId: string | number, groupId: string | number | null) => {
    const next = new Map(assignments.value)
    if (groupId === null) next.delete(String(studentId))
    else next.set(String(studentId), groupId)
    assignments.value = next
  }

  const groupIdFor = (studentId: string | number) =>
    assignments.value.get(String(studentId)) ?? null

  const confirm = async (): Promise<boolean> => {
    if (confirming.value) return false

    const payload = Array.from(assignments.value.entries())
      .map(([studentId, groupId]) => ({
        studentId: Number(studentId),
        groupId: Number(groupId)
      }))
      // The endpoint keys on integer ids; anything non-numeric is a synthetic
      // row and would 400 the whole batch.
      // `> 0`, not `Number.isFinite`: Number('') is 0, which is finite, so a
      // missing id would otherwise be posted as student 0.
      .filter((entry) => entry.studentId > 0 && entry.groupId > 0)

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
    recommendations,
    unmatchedStudents,
    notFullGroups,
    recommendedCount,
    assignmentCount,
    isEmpty,
    run,
    reset,
    confirm,
    assignStudent,
    groupIdFor
  }
}
