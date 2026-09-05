/**
 * @file adminMatching.ts
 * @description Types and response normalisation for the admin matching tabs.
 *
 * Why this exists: `GET /api/v1/admin/match/student/` does not return a stable
 * shape. `MatchStudentView` wraps the algorithm result in snake_case keys
 * (`unmatched_students`, `not_full_groups`) while nested student/group records
 * come back with a mix of `country_name`/`country` and `year_level`/`yearLevel`,
 * and `recommendations` is sometimes a flat per-student list and sometimes
 * already grouped per target group.
 *
 * The reference React app absorbs all of this in a Zod schema
 * (adminweb/src/schema/match.ts). This app has no Zod, so the same aliasing and
 * the same flat-to-grouped pivot are done by hand here — deliberately in one
 * module so the panels and composables only ever see the normalised shape.
 */

// ---------------------------------------------------------------------------
// Normalised types (what the UI consumes)
// ---------------------------------------------------------------------------

export interface MatchStudent {
  id: string | number
  name: string
  country: string | null
  yearLevel: number | null
  interests: string[]
}

export interface MatchTutor {
  id: string | number
  name: string
}

export interface MatchScoreBreakdown {
  baseScore: number
  yearPenalty: number
  countryPenalty: number
  timezonePenalty: number
  sizeBonus: number
  totalPenalty: number
  objectiveScore: number
}

export interface RecommendedStudent {
  student: MatchStudent
  reason: string
  score: number
  scoreBreakdown: MatchScoreBreakdown | null
}

/** One target group with the students the algorithm proposes adding to it. */
export interface MatchRecommendationGroup {
  id: string | number
  groupName: string
  maxSize: number | null
  tutor: MatchTutor | null
  existingStudents: MatchStudent[]
  recommendStudents: RecommendedStudent[]
}

export interface NotFullGroup {
  id: string | number
  groupName: string
  maxSize: number | null
  tutor: MatchTutor | null
  existingStudents: MatchStudent[]
  studentCount: number
  availableSeats: number
}

export interface StudentMatchData {
  recommendations: MatchRecommendationGroup[]
  unmatchedStudents: RecommendedStudent[]
  notFullGroups: NotFullGroup[]
}

/** A student the admin has moved into a group but not yet confirmed. */
export interface PendingAssignment {
  studentId: number
  groupId: number | string
}

// ---------------------------------------------------------------------------
// Primitives
// ---------------------------------------------------------------------------

type Raw = Record<string, unknown>

const isRecord = (value: unknown): value is Raw =>
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)

/** First defined value among `keys`. Absorbs the snake_case/camelCase drift. */
const pick = (source: Raw, ...keys: string[]): unknown => {
  for (const key of keys) {
    if (source[key] !== undefined && source[key] !== null) return source[key]
  }
  return undefined
}

const toText = (value: unknown, fallback = ''): string =>
  typeof value === 'string' ? value : value == null ? fallback : String(value)

const toNumberOrNull = (value: unknown): number | null => {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

const toNumber = (value: unknown, fallback = 0): number =>
  toNumberOrNull(value) ?? fallback

/**
 * Interests arrive either as plain strings or as `{ interestDesc }` /
 * `{ name }` objects depending on which query built the row.
 */
const toInterests = (value: unknown): string[] => {
  if (!Array.isArray(value)) return []
  return value
    .map((entry) => {
      if (typeof entry === 'string') return entry
      if (isRecord(entry)) return toText(pick(entry, 'interestDesc', 'name'))
      return ''
    })
    .filter(Boolean)
}

// ---------------------------------------------------------------------------
// Record normalisers
// ---------------------------------------------------------------------------

const toStudent = (value: unknown): MatchStudent => {
  const raw = isRecord(value) ? value : {}
  const first = toText(pick(raw, 'firstName', 'first_name'))
  const last = toText(pick(raw, 'lastName', 'last_name'))
  const fallbackName = `${first} ${last}`.trim()

  return {
    id: (pick(raw, 'id', 'studentUserId', 'user_id') as string | number) ?? '',
    name: toText(pick(raw, 'name'), fallbackName) || 'Unknown student',
    country: toNullableText(pick(raw, 'country', 'country_name', 'countryName')),
    // `yearlevel` (no separator) is a real spelling in the algorithm's output.
    yearLevel: toNumberOrNull(pick(raw, 'yearLevel', 'year_level', 'yearlevel')),
    interests: toInterests(pick(raw, 'interests'))
  }
}

const toNullableText = (value: unknown): string | null => {
  const text = toText(value)
  return text ? text : null
}

const toTutor = (value: unknown): MatchTutor | null => {
  if (!isRecord(value)) return null
  const id = pick(value, 'id', 'tutor_user_id', 'tutorUserId')
  const name = toText(pick(value, 'name', 'tutor_name', 'tutorName'))
  if (id === undefined && !name) return null
  return { id: (id as string | number) ?? '', name: name || 'Unassigned' }
}

const toScoreBreakdown = (value: unknown): MatchScoreBreakdown | null => {
  if (!isRecord(value)) return null
  return {
    baseScore: toNumber(pick(value, 'baseScore', 'base_score')),
    yearPenalty: toNumber(pick(value, 'yearPenalty', 'year_penalty')),
    countryPenalty: toNumber(pick(value, 'countryPenalty', 'country_penalty')),
    timezonePenalty: toNumber(pick(value, 'timezonePenalty', 'timezone_penalty')),
    sizeBonus: toNumber(pick(value, 'sizeBonus', 'size_bonus')),
    totalPenalty: toNumber(pick(value, 'totalPenalty', 'total_penalty')),
    objectiveScore: toNumber(pick(value, 'objectiveScore', 'objective_score'))
  }
}

const toRecommendedStudent = (value: unknown): RecommendedStudent => {
  const raw = isRecord(value) ? value : {}
  return {
    student: toStudent(pick(raw, 'student') ?? raw),
    reason: toText(pick(raw, 'reason')),
    score: toNumber(pick(raw, 'score')),
    scoreBreakdown: toScoreBreakdown(pick(raw, 'scoreBreakdown', 'score_breakdown'))
  }
}

const toStudentList = (value: unknown): MatchStudent[] =>
  Array.isArray(value) ? value.map(toStudent) : []

const toGroupShell = (raw: Raw) => ({
  id: (pick(raw, 'id', 'groupId', 'group_id') as string | number) ?? '',
  groupName: toText(pick(raw, 'groupName', 'group_name'), 'Unnamed group'),
  maxSize: toNumberOrNull(pick(raw, 'maxSize', 'max_size')),
  tutor: toTutor(pick(raw, 'tutor')),
  existingStudents: toStudentList(
    pick(raw, 'existingStudents', 'groupStudent', 'group_student')
  )
})

const toNotFullGroup = (value: unknown): NotFullGroup => {
  const raw = isRecord(value) ? value : {}
  const shell = toGroupShell(raw)
  const studentCount = toNumber(
    pick(raw, 'studentCount', 'student_count'),
    shell.existingStudents.length
  )
  const maxSize = shell.maxSize ?? 5
  return {
    ...shell,
    studentCount,
    availableSeats: toNumber(
      pick(raw, 'availableSeats', 'available_seats'),
      Math.max(0, maxSize - studentCount)
    )
  }
}

// ---------------------------------------------------------------------------
// Flat -> grouped pivot
// ---------------------------------------------------------------------------

/**
 * The algorithm can emit one entry per student (`{ student, recommendGroup }`)
 * rather than one entry per group. Pivot those into per-group buckets, and send
 * any student with no `recommendGroup` to the unmatched list.
 *
 * Mirrors `groupFlatRecommendations` in adminweb/src/schema/match.ts.
 */
const pivotFlatRecommendations = (
  entries: Raw[]
): { recommendations: MatchRecommendationGroup[]; unmatchedStudents: RecommendedStudent[] } => {
  const groupsById = new Map<string, MatchRecommendationGroup>()
  const unmatchedStudents: RecommendedStudent[] = []

  for (const entry of entries) {
    const recommended = toRecommendedStudent(entry)
    const groupRaw = pick(entry, 'recommendGroup', 'recommend_group')

    if (!isRecord(groupRaw)) {
      unmatchedStudents.push(recommended)
      continue
    }

    const shell = toGroupShell(groupRaw)
    const key = String(shell.id)
    const existing = groupsById.get(key)

    if (existing) {
      existing.recommendStudents.push(recommended)
      continue
    }

    groupsById.set(key, { ...shell, recommendStudents: [recommended] })
  }

  return { recommendations: [...groupsById.values()], unmatchedStudents }
}

const toGroupedRecommendation = (value: unknown): MatchRecommendationGroup => {
  const raw = isRecord(value) ? value : {}
  return {
    ...toGroupShell(raw),
    recommendStudents: Array.isArray(pick(raw, 'recommendStudents', 'recommend_students'))
      ? (pick(raw, 'recommendStudents', 'recommend_students') as unknown[]).map(
          toRecommendedStudent
        )
      : []
  }
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

/**
 * Normalise the `data` payload of `GET /match/student/`.
 *
 * Accepts every shape the endpoint is known to return:
 *  - a bare array of flat per-student recommendations
 *  - `{ recommendations, unmatched_students, not_full_groups }` where
 *    `recommendations` is flat
 *  - the same object where `recommendations` is already grouped
 */
export const normalizeStudentMatchData = (payload: unknown): StudentMatchData => {
  if (Array.isArray(payload)) {
    return { ...pivotFlatRecommendations(payload as Raw[]), notFullGroups: [] }
  }

  if (!isRecord(payload)) {
    return { recommendations: [], unmatchedStudents: [], notFullGroups: [] }
  }

  const rawRecommendations = pick(payload, 'recommendations')
  const entries: Raw[] = Array.isArray(rawRecommendations)
    ? (rawRecommendations.filter(isRecord) as Raw[])
    : []

  const notFullGroups = Array.isArray(pick(payload, 'notFullGroups', 'not_full_groups'))
    ? (pick(payload, 'notFullGroups', 'not_full_groups') as unknown[]).map(toNotFullGroup)
    : []

  const declaredUnmatched = Array.isArray(pick(payload, 'unmatchedStudents', 'unmatched_students'))
    ? (pick(payload, 'unmatchedStudents', 'unmatched_students') as unknown[]).map(
        toRecommendedStudent
      )
    : []

  // A `student` key means the flat per-student shape; otherwise it is grouped.
  const flatEntries = entries.filter((entry) => 'student' in entry)

  if (flatEntries.length > 0) {
    const pivoted = pivotFlatRecommendations(flatEntries)
    return {
      recommendations: pivoted.recommendations,
      // Prefer the server's own unmatched list when it sent one.
      unmatchedStudents: declaredUnmatched.length > 0 ? declaredUnmatched : pivoted.unmatchedStudents,
      notFullGroups
    }
  }

  return {
    recommendations: entries.map(toGroupedRecommendation),
    unmatchedStudents: declaredUnmatched,
    notFullGroups
  }
}

/** `POST /match/confirm/` returns `{ assigned_count }` or `{ assignedCount }`. */
export const normalizeAssignedCount = (payload: unknown): number => {
  if (!isRecord(payload)) return 0
  return toNumber(pick(payload, 'assignedCount', 'assigned_count'))
}
