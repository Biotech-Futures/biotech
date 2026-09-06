/**
 * @file adminMatching.ts
 * @description Zod schemas for the admin matching endpoints.
 *
 * Why validation rather than coercion: `GET /match/student/` has an unstable
 * contract. It wraps results in snake_case keys (`unmatched_students`,
 * `not_full_groups`), nested records arrive with mixed casing
 * (`country_name`/`country`, `year_level`/`yearLevel`/`yearlevel`), and
 * `recommendations` is sometimes a flat per-student list and sometimes already
 * grouped per target group.
 *
 * An earlier hand-written normaliser coerced all of that into "something
 * usable", which meant a record missing an id silently became `id: ''` -> `0`
 * and was posted to `/match/confirm/`. These tabs write live assignments, so a
 * loud failure at the boundary beats a plausible-looking wrong one downstream.
 *
 * Mirrors adminweb/src/schema/match.ts and schema/mentorMatch.ts.
 */
import { z } from 'zod'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === 'object' && !Array.isArray(value)

/** Copy `from` keys onto their `to` names when `to` is absent. */
const withAliases = (value: unknown, aliases: Record<string, string>): unknown => {
  if (!isRecord(value)) return value
  const next = { ...value }
  for (const [from, to] of Object.entries(aliases)) {
    if (next[to] === undefined && next[from] !== undefined) next[to] = next[from]
  }
  return next
}

/**
 * Ids must survive a round trip to `/match/confirm/`, which keys on integers.
 * `z.coerce.number()` turns '' and null into 0, so `.positive()` is what
 * actually rejects a missing id rather than letting it through as student 0.
 */
const numericId = z.coerce.number().int().positive()

/** Interests arrive as plain strings or as `{ interestDesc }` / `{ name }`. */
const interestList = z.preprocess((value) => {
  if (!Array.isArray(value)) return []
  return value
    .map((entry) => {
      if (typeof entry === 'string') return entry
      if (isRecord(entry)) return entry.interestDesc ?? entry.name ?? ''
      return ''
    })
    .filter((entry) => typeof entry === 'string' && entry.length > 0)
}, z.array(z.string()))

// ---------------------------------------------------------------------------
// Student matching
// ---------------------------------------------------------------------------

const studentSchema = z.preprocess(
  (value) => {
    const raw = withAliases(value, {
      country_name: 'country',
      countryName: 'country',
      year_level: 'yearLevel',
      yearlevel: 'yearLevel',
      user_id: 'id',
      studentUserId: 'id'
    })
    if (!isRecord(raw)) return raw
    // Some queries return first/last rather than a composed display name.
    if (raw.name === undefined) {
      const composed = `${raw.firstName ?? raw.first_name ?? ''} ${raw.lastName ?? raw.last_name ?? ''}`.trim()
      if (composed) return { ...raw, name: composed }
    }
    return raw
  },
  z.object({
    id: numericId,
    name: z.string().min(1),
    country: z.string().nullable().default(null),
    yearLevel: z.number().int().nullable().default(null),
    interests: interestList.default([])
  })
)

const tutorSchema = z.preprocess(
  (value) => withAliases(value, { tutor_user_id: 'id', tutor_name: 'name' }),
  z
    .object({
      id: z.union([z.string(), z.number()]),
      name: z.string()
    })
    .nullable()
    .default(null)
)

const scoreBreakdownSchema = z
  .object({
    baseScore: z.number(),
    yearPenalty: z.number(),
    countryPenalty: z.number(),
    timezonePenalty: z.number(),
    sizeBonus: z.number(),
    totalPenalty: z.number(),
    objectiveScore: z.number()
  })
  .nullable()
  .default(null)

const recommendedStudentSchema = z.object({
  student: studentSchema,
  reason: z.string().default(''),
  score: z.number().default(0),
  scoreBreakdown: scoreBreakdownSchema
})

const groupShellAliases = (value: unknown) =>
  withAliases(value, {
    group_id: 'id',
    groupId: 'id',
    group_name: 'groupName',
    max_size: 'maxSize',
    groupStudent: 'existingStudents',
    group_student: 'existingStudents'
  })

// Kept unwrapped so the grouped/not-full variants below can `.extend()` it —
// z.preprocess() returns a wrapper that has no object methods.
const groupShellObject = z.object({
  id: numericId,
  groupName: z.string().min(1),
  maxSize: z.number().int().nullable().default(null),
  tutor: tutorSchema,
  existingStudents: z.array(studentSchema).default([])
})

const groupShellSchema = z.preprocess(groupShellAliases, groupShellObject)

/** One entry per student, with the group the matcher proposes for them. */
const flatRecommendationSchema = z.preprocess(
  (value) => withAliases(value, { recommend_group: 'recommendGroup' }),
  z.object({
    student: studentSchema,
    recommendGroup: groupShellSchema.nullable().default(null),
    reason: z.string().default(''),
    score: z.number().default(0),
    scoreBreakdown: scoreBreakdownSchema
  })
)

/** One entry per group, already carrying its proposed students. */
const groupedRecommendationSchema = z.preprocess(
  (value) => withAliases(groupShellAliases(value), { recommend_students: 'recommendStudents' }),
  groupShellObject.extend({
    recommendStudents: z.array(recommendedStudentSchema).default([])
  })
)

const notFullGroupSchema = z.preprocess(
  (value) =>
    withAliases(groupShellAliases(value), {
      student_count: 'studentCount',
      available_seats: 'availableSeats'
    }),
  groupShellObject.extend({
    studentCount: z.number().int().nonnegative().default(0),
    availableSeats: z.number().int().nonnegative().default(0)
  })
)

export type MatchStudent = z.infer<typeof studentSchema>
export type MatchTutor = z.infer<typeof tutorSchema>
export type MatchScoreBreakdown = z.infer<typeof scoreBreakdownSchema>
export type RecommendedStudent = z.infer<typeof recommendedStudentSchema>
export type MatchRecommendationGroup = z.infer<typeof groupedRecommendationSchema>
export type NotFullGroup = z.infer<typeof notFullGroupSchema>

export interface StudentMatchData {
  recommendations: MatchRecommendationGroup[]
  unmatchedStudents: RecommendedStudent[]
  notFullGroups: NotFullGroup[]
}

/**
 * Pivot flat per-student entries into per-group buckets. A student with no
 * `recommendGroup` had nowhere to go and belongs in the unmatched list.
 */
const pivotFlat = (
  entries: z.infer<typeof flatRecommendationSchema>[]
): { recommendations: MatchRecommendationGroup[]; unmatchedStudents: RecommendedStudent[] } => {
  const byGroupId = new Map<string, MatchRecommendationGroup>()
  const unmatchedStudents: RecommendedStudent[] = []

  for (const entry of entries) {
    const recommended: RecommendedStudent = {
      student: entry.student,
      reason: entry.reason,
      score: entry.score,
      scoreBreakdown: entry.scoreBreakdown
    }

    if (!entry.recommendGroup) {
      unmatchedStudents.push(recommended)
      continue
    }

    const key = String(entry.recommendGroup.id)
    const existing = byGroupId.get(key)
    if (existing) {
      existing.recommendStudents.push(recommended)
      continue
    }

    byGroupId.set(key, { ...entry.recommendGroup, recommendStudents: [recommended] })
  }

  return { recommendations: [...byGroupId.values()], unmatchedStudents }
}

const studentMatchDataSchema = z
  .preprocess(
    (value) =>
      withAliases(value, {
        unmatched_students: 'unmatchedStudents',
        not_full_groups: 'notFullGroups'
      }),
    z.union([
      // Bare array of flat recommendations.
      z.array(flatRecommendationSchema),
      z.object({
        recommendations: z
          .array(z.union([groupedRecommendationSchema, flatRecommendationSchema]))
          .default([]),
        unmatchedStudents: z.array(recommendedStudentSchema).default([]),
        notFullGroups: z.array(notFullGroupSchema).default([])
      })
    ])
  )
  .transform<StudentMatchData>((value) => {
    if (Array.isArray(value)) {
      return { ...pivotFlat(value), notFullGroups: [] }
    }

    const flat = value.recommendations.filter(
      (entry): entry is z.infer<typeof flatRecommendationSchema> => 'student' in entry
    )

    if (flat.length > 0) {
      const pivoted = pivotFlat(flat)
      return {
        recommendations: pivoted.recommendations,
        // Prefer the server's own list when it sent one.
        unmatchedStudents:
          value.unmatchedStudents.length > 0 ? value.unmatchedStudents : pivoted.unmatchedStudents,
        notFullGroups: value.notFullGroups
      }
    }

    return {
      recommendations: value.recommendations.filter(
        (entry): entry is MatchRecommendationGroup => !('student' in entry)
      ),
      unmatchedStudents: value.unmatchedStudents,
      notFullGroups: value.notFullGroups
    }
  })

// ---------------------------------------------------------------------------
// Mentor matching
//
// This endpoint already returns clean camelCase, so there is no aliasing here —
// the schema exists to catch a shape change rather than to reconcile one.
// ---------------------------------------------------------------------------

const mentorGroupStudentSchema = z.object({
  name: z.string(),
  hasLoggedIn: z.boolean().default(false),
  interests: interestList.default([])
})

const mentorMatchGroupSchema = z.object({
  groupId: numericId,
  groupName: z.string().min(1),
  countryName: z.string().nullable().default(null),
  studentInterests: interestList.default([]),
  studentCount: z.number().int().nonnegative().default(0),
  students: z.array(mentorGroupStudentSchema).optional()
})

const recommendedMentorSchema = z
  .object({
    mentorId: numericId,
    name: z.string().min(1),
    countryName: z.string().nullable().default(null),
    institution: z.string().nullable().default(null),
    interests: interestList.default([]),
    remainingCapacity: z.number().int().default(0)
  })
  .nullable()
  .default(null)

const mentorScoreBreakdownSchema = z
  .object({
    baseScore: z.number(),
    countryPenalty: z.number(),
    interestBonus: z.number(),
    timezonePenalty: z.number(),
    capacityBonus: z.number(),
    objectiveScore: z.number()
  })
  .nullable()
  .default(null)

const mentorGroupRecommendationSchema = z.object({
  group: mentorMatchGroupSchema,
  recommendedMentor: recommendedMentorSchema,
  reason: z.string().default(''),
  score: z.number().default(0),
  scoreBreakdown: mentorScoreBreakdownSchema
})

const mentorRecommendationsSchema = z.array(mentorGroupRecommendationSchema)

export type MentorMatchGroupStudent = z.infer<typeof mentorGroupStudentSchema>
export type MentorMatchGroup = z.infer<typeof mentorMatchGroupSchema>
export type RecommendedMentor = z.infer<typeof recommendedMentorSchema>
export type MentorScoreBreakdown = z.infer<typeof mentorScoreBreakdownSchema>
export type MentorGroupRecommendation = z.infer<typeof mentorGroupRecommendationSchema>

// ---------------------------------------------------------------------------
// Public parse helpers
// ---------------------------------------------------------------------------

export type ParseResult<T> = { ok: true; data: T } | { ok: false; message: string }

/** First few issues, with their paths — enough to find the offending field. */
const describeIssues = (error: z.ZodError): string => {
  const shown = error.issues.slice(0, 3).map((issue) => {
    const path = issue.path.length > 0 ? issue.path.join('.') : 'response'
    return `${path}: ${issue.message}`
  })
  const extra = error.issues.length - shown.length
  return shown.join('; ') + (extra > 0 ? ` (+${extra} more)` : '')
}

const toResult = <T>(result: z.ZodSafeParseResult<T>, label: string): ParseResult<T> =>
  result.success
    ? { ok: true, data: result.data }
    : { ok: false, message: `${label} returned an unexpected format — ${describeIssues(result.error)}` }

export const parseStudentMatchData = (payload: unknown): ParseResult<StudentMatchData> =>
  toResult(studentMatchDataSchema.safeParse(payload), 'Student matching')

export const parseMentorRecommendations = (
  payload: unknown
): ParseResult<MentorGroupRecommendation[]> =>
  toResult(mentorRecommendationsSchema.safeParse(payload), 'Mentor matching')

/** `POST /match/confirm/` returns `{ assigned_count }` or `{ assignedCount }`. */
export const normalizeAssignedCount = (payload: unknown): number => {
  const parsed = z
    .preprocess(
      (value) => withAliases(value, { assigned_count: 'assignedCount' }),
      z.object({ assignedCount: z.number().int().nonnegative().default(0) })
    )
    .safeParse(payload)
  return parsed.success ? parsed.data.assignedCount : 0
}
