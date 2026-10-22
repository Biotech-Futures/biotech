import type { SummaryRow } from '@/utils/analyticsExport'
import type { DemoMentor, MentorEvent } from '@/types/analytics'

export interface MetricBucket {
  label: string
  value: number
}
export interface MentorRange {
  start: string
  end: string
}
export const percent = (value: number, total: number) =>
  total ? Math.round((value / total) * 1000) / 10 : 0
const DAY = 86400000
const dateNumber = (date: string) => Date.parse(`${date}T00:00:00Z`)

export function validRange(range: MentorRange) {
  const validDate = (value: string) =>
    /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    Number.isFinite(dateNumber(value)) &&
    new Date(dateNumber(value)).toISOString().slice(0, 10) === value
  return validDate(range.start) && validDate(range.end) && range.start <= range.end
}

// Programme limits: a mentor supports at most 5 groups, and each group has at
// most 5 students, so a mentor supports at most 25 students.
export const MAX_GROUPS_PER_MENTOR = 5
export const MAX_STUDENTS_PER_MENTOR = 25

/** True unless the mentor source says the account is not activated. */
export const isActivatedMentor = (mentor: DemoMentor) => mentor.accountActive ?? mentor.status === 'active'

export function mentorSnapshot(
  mentors: DemoMentor[],
  events: MentorEvent[],
  asOf: string,
  // Login recency is measured to this date (today by default), because the
  // mentor's last login comes from the account rather than the event window.
  loginAsOf = new Date().toISOString().slice(0, 10),
) {
  const eventLogins = new Map<string, string>()
  for (const event of events) {
    if (
      event.logins > 0 &&
      event.date <= asOf &&
      event.date > (eventLogins.get(event.mentorId) ?? '')
    )
      eventLogins.set(event.mentorId, event.date)
  }
  const rows = mentors.map((mentor) => {
    const groups = new Set(mentor.groupIds).size
    // Prefer the account's own last login; login events are only a fallback
    // for sources that do not send it.
    const lastLogin = mentor.lastLogin !== undefined
      ? (mentor.lastLogin ? mentor.lastLogin.slice(0, 10) : null)
      : (eventLogins.get(mentor.id) ?? null)
    const recencyDate = mentor.lastLogin !== undefined ? loginAsOf : asOf
    return {
      ...mentor,
      groups,
      students: new Set(mentor.studentIds).size,
      lastLogin,
      daysSinceLogin: lastLogin
        ? Math.max(0, Math.floor((dateNumber(recencyDate) - dateNumber(lastLogin)) / DAY))
        : null,
    }
  })
  const count = (predicate: (mentor: (typeof rows)[number]) => boolean) =>
    rows.filter(predicate).length
  // Buckets past the programme limit only appear when someone is over it.
  const withOverLimit = (buckets: MetricBucket[], over: MetricBucket) =>
    over.value > 0 ? [...buckets, over] : buckets
  const assigned = count((m) => m.groups > 0)
  const status = ['active', 'inactive', 'onboarding'].map((label) => ({
    label: label[0]!.toUpperCase() + label.slice(1),
    value: count((m) => m.status === label),
  }))
  const background = (['industry', 'undergraduate', 'postgraduate', 'hdr', 'unknown'] as const).map((key) => ({
    label: key === 'hdr' ? 'HDR' : key[0]!.toUpperCase() + key.slice(1),
    value: count((m) => m.background === key),
  }))
  // Capacity describes the activated mentor pool: their configured group
  // capacity against the groups they currently support.
  const activated = rows.filter(isActivatedMentor)
  const capacity = [
    { label: 'Available capacity', value: activated.filter((m) => m.groups < m.capacity).length },
    { label: 'At capacity', value: activated.filter((m) => m.groups === m.capacity).length },
    { label: 'Over capacity', value: activated.filter((m) => m.groups > m.capacity).length },
  ]
  const totalSlots = activated.reduce((sum, m) => sum + m.capacity, 0)
  const usedSlots = activated.reduce((sum, m) => sum + m.groups, 0)
  const capacityPool = {
    activatedMentors: activated.length,
    totalSlots,
    usedSlots,
    openSlots: activated.reduce((sum, m) => sum + Math.max(m.capacity - m.groups, 0), 0),
    utilisation: percent(usedSlots, totalSlots),
  }
  const groups = withOverLimit(
    Array.from({ length: MAX_GROUPS_PER_MENTOR + 1 }, (_, size) => ({
      label: String(size),
      value: count((m) => m.groups === size),
    })),
    { label: `Over ${MAX_GROUPS_PER_MENTOR}`, value: count((m) => m.groups > MAX_GROUPS_PER_MENTOR) },
  )
  const students = withOverLimit(
    [
      { label: '0', value: count((m) => m.students === 0) },
      ...[1, 6, 11, 16, 21].map((from) => ({
        label: `${from}–${from + 4}`,
        value: count((m) => m.students >= from && m.students <= from + 4),
      })),
    ],
    { label: `Over ${MAX_STUDENTS_PER_MENTOR}`, value: count((m) => m.students > MAX_STUDENTS_PER_MENTOR) },
  )
  const lastLogin = [
    { label: '0–7 days', value: count((m) => m.daysSinceLogin !== null && m.daysSinceLogin <= 7) },
    {
      label: '8–30 days',
      value: count(
        (m) => m.daysSinceLogin !== null && m.daysSinceLogin >= 8 && m.daysSinceLogin <= 30,
      ),
    },
    {
      label: '31–90 days',
      value: count(
        (m) => m.daysSinceLogin !== null && m.daysSinceLogin >= 31 && m.daysSinceLogin <= 90,
      ),
    },
    { label: '90+ days', value: count((m) => m.daysSinceLogin !== null && m.daysSinceLogin > 90) },
    { label: 'Never logged in', value: count((m) => m.daysSinceLogin === null) },
  ]
  return {
    rows,
    total: rows.length,
    assigned,
    unassigned: rows.length - assigned,
    utilisation: percent(assigned, rows.length),
    averageStudents: assigned
      ? Math.round(
          (rows.filter((m) => m.groups > 0).reduce((sum, m) => sum + m.students, 0) / assigned) *
            10,
        ) / 10
      : 0,
    status,
    background,
    capacity,
    groups,
    students,
    lastLogin,
    capacityPool,
    coverage: [
      { label: 'Supporting groups', value: assigned },
      { label: 'Without a group', value: rows.length - assigned },
    ],
    insights: [
      {
        label: 'Unassigned mentors',
        value: rows.length - assigned,
        detail: 'No current group assignments.',
      },
      {
        label: 'Inactive accounts',
        value: count((m) => m.status === 'inactive'),
        detail: 'Explicit account status, not recent activity.',
      },
      {
        label: 'Near capacity',
        value: activated.filter((m) => m.capacity > 0 && m.groups === m.capacity - 1).length,
        detail: 'Activated mentors one group below their configured capacity.',
      },
      {
        label: 'Over capacity',
        value: capacity[2]!.value,
        detail: 'Activated mentors with more groups than their configured capacity.',
      },
      {
        label: 'No login for more than 30 days',
        value: count((m) => m.daysSinceLogin !== null && m.daysSinceLogin > 30),
        detail: 'Last account login was more than 30 days ago.',
      },
      {
        label: 'Never logged in',
        value: count((m) => m.daysSinceLogin === null),
        detail: 'No login recorded on the mentor account.',
      },
    ],
  }
}

export function mentorActivity(mentors: DemoMentor[], events: MentorEvent[], range: MentorRange) {
  const monthly = new Map<string, { ids: Set<string>; messages: number; logins: number }>()
  if (!validRange(range)) return { monthly: [], ranking: [], eventCount: 0 }
  // Keep arbitrary user-entered date spans bounded for charts and exports.
  const start = new Date(dateNumber(range.start))
  start.setUTCDate(1)
  const end = new Date(dateNumber(range.end))
  end.setUTCDate(1)
  if (
    (end.getUTCFullYear() - start.getUTCFullYear()) * 12 +
      end.getUTCMonth() -
      start.getUTCMonth() >=
    24
  )
    return { monthly: [], ranking: [], eventCount: 0 }
  for (
    const cursor = new Date(start);
    cursor <= end;
    cursor.setUTCMonth(cursor.getUTCMonth() + 1)
  ) {
    monthly.set(cursor.toISOString().slice(0, 7), { ids: new Set(), messages: 0, logins: 0 })
  }
  const names = new Map(mentors.map((m) => [m.id, m.name]))
  const totals = new Map<string, number>()
  let eventCount = 0
  for (const event of events) {
    if (!names.has(event.mentorId) || event.date < range.start || event.date > range.end) continue
    const month = monthly.get(event.date.slice(0, 7))!
    if (event.logins > 0 || event.messages > 0) {
      month.ids.add(event.mentorId)
      eventCount++
    }
    month.messages += event.messages
    month.logins += event.logins
    totals.set(event.mentorId, (totals.get(event.mentorId) ?? 0) + event.messages)
  }
  return {
    monthly: [...monthly].map(([month, data]) => ({
      month,
      active: data.ids.size,
      messages: data.messages,
      logins: data.logins,
    })),
    // Every activated mentor, including those without messages, so the list
    // can be read from either end; highest first by default.
    ranking: mentors
      .filter(isActivatedMentor)
      .map((mentor) => ({ id: mentor.id, name: mentor.name, messages: totals.get(mentor.id) ?? 0 }))
      .sort((a, b) => b.messages - a.messages || a.name.localeCompare(b.name) || a.id.localeCompare(b.id)),
    eventCount,
  }
}

/** Summary export rows: every figure on the Mentors page. */
export function mentorsSummaryRows(
  snapshot: ReturnType<typeof mentorSnapshot>,
  activity: ReturnType<typeof mentorActivity>,
  available: { groups?: boolean; background?: boolean; activity?: boolean } = {},
): SummaryRow[] {
  const groupsAvailable = available.groups !== false
  const activityAvailable = available.activity !== false
  const unavailable = (section: string): SummaryRow =>
    ({ section, metric: 'Availability', value: '', notes: 'The data for this section could not be loaded' })
  const rows: SummaryRow[] = [
    { section: 'Mentors', metric: 'Total mentors', value: snapshot.total, unit: 'mentors' },
  ]
  if (groupsAvailable) {
    const pool = snapshot.capacityPool
    rows.push(
      { section: 'Mentors', metric: 'Mentors with a group', value: snapshot.assigned, unit: 'mentors' },
      { section: 'Mentors', metric: 'Mentors without a group', value: snapshot.unassigned, unit: 'mentors' },
      { section: 'Mentors', metric: 'Mentors with a group (%)', value: snapshot.utilisation, unit: '%', notes: 'Share of all mentors' },
      {
        section: 'Mentors', metric: 'Average students per mentor', value: snapshot.averageStudents, unit: 'students',
        notes: 'Mentors with a group; unique students',
      },
      { section: 'Capacity pool', metric: 'Activated mentors', value: pool.activatedMentors, unit: 'mentors', notes: 'Account status active' },
      { section: 'Capacity pool', metric: 'Total capacity', value: pool.totalSlots, unit: 'groups', notes: "Sum of activated mentors' configured capacity" },
      { section: 'Capacity pool', metric: 'Groups supported', value: pool.usedSlots, unit: 'groups' },
      { section: 'Capacity pool', metric: 'Open slots', value: pool.openSlots, unit: 'groups' },
      { section: 'Capacity pool', metric: 'Capacity used (%)', value: pool.utilisation, unit: '%', notes: 'Groups supported / total capacity' },
    )
  } else {
    rows.push(unavailable('Capacity pool'))
  }
  const sections: Array<[string, MetricBucket[], boolean, number, string]> = [
    ['Mentor status', snapshot.status, true, snapshot.total, 'mentors'],
    ['Background', snapshot.background, available.background !== false, snapshot.total, 'mentors'],
    ['Capacity split', snapshot.capacity, groupsAvailable, snapshot.capacityPool.activatedMentors, 'activated mentors'],
    ['Groups per mentor', snapshot.groups, groupsAvailable, snapshot.total, 'mentors'],
    ['Students per mentor', snapshot.students, groupsAvailable, snapshot.total, 'mentors'],
    // Last login comes from the mentor accounts, not the message activity.
    ['Last login', snapshot.lastLogin, true, snapshot.total, 'mentors'],
    ['Coverage', snapshot.coverage, groupsAvailable, snapshot.total, 'mentors'],
  ]
  for (const [section, buckets, isAvailable, base, baseLabel] of sections) {
    if (!isAvailable) {
      rows.push(unavailable(section))
      continue
    }
    for (const bucket of buckets) {
      rows.push({ section, metric: bucket.label, value: bucket.value, unit: 'mentors', notes: `${percent(bucket.value, base)}% of ${baseLabel}` })
    }
  }
  if (activityAvailable) {
    for (const point of activity.monthly) {
      rows.push(
        { section: 'Monthly activity', metric: `${point.month}: active mentors`, value: point.active, unit: 'mentors', notes: 'A login or a message' },
        { section: 'Monthly activity', metric: `${point.month}: messages`, value: point.messages, unit: 'messages' },
        { section: 'Monthly activity', metric: `${point.month}: logins`, value: point.logins, unit: 'logins' },
      )
    }
    activity.ranking.forEach((mentor, index) => rows.push({
      section: 'Mentor activity', metric: mentor.name, value: mentor.messages, unit: 'messages', notes: `Rank ${index + 1} in the date range`,
    }))
  } else {
    rows.push(unavailable('Monthly activity'))
  }
  for (const item of snapshot.insights) {
    const missing = !groupsAvailable && ['Unassigned mentors', 'Near capacity', 'Over capacity'].includes(item.label)
    rows.push(missing
      ? { section: 'Key insights', metric: item.label, value: '', notes: 'The data for this metric could not be loaded' }
      : { section: 'Key insights', metric: item.label, value: item.value, unit: 'mentors', notes: item.detail })
  }
  return rows
}
