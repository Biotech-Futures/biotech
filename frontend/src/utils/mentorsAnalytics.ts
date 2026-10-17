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

export function mentorsCsv(
  snapshot: ReturnType<typeof mentorSnapshot>,
  activity: ReturnType<typeof mentorActivity>,
  range: MentorRange,
  asOf: string,
  available: { groups?: boolean; background?: boolean; activity?: boolean } = {},
) {
  const groupsAvailable = available.groups !== false
  const activityAvailable = available.activity !== false
  const unknown = 'Unavailable'
  const rows: (string | number)[][] = [
    ['Section', 'Metric', 'Value', 'Detail'],
    ['Metadata', 'Source', 'Django analytics API', 'Local database-backed data'],
    ['Metadata', 'Snapshot date', asOf, 'UTC'],
    ['Metadata', 'Activity start', range.start, 'Inclusive UTC date'],
    ['Metadata', 'Activity end', range.end, 'Inclusive UTC date'],
    ['Summary', 'Total Mentors', snapshot.total],
    ['Summary', 'Mentor Utilisation (%)', groupsAvailable ? snapshot.utilisation : unknown],
    ['Summary', 'Assigned Mentors', groupsAvailable ? snapshot.assigned : unknown],
    ['Summary', 'Unassigned Mentors', groupsAvailable ? snapshot.unassigned : unknown],
    [
      'Summary',
      'Average Students per Mentor',
      groupsAvailable ? snapshot.averageStudents : unknown,
      'Assigned mentors only; unique students per mentor',
    ],
  ]
  for (const [section, buckets] of Object.entries({
    Status: snapshot.status,
    Background: snapshot.background,
    Capacity: snapshot.capacity,
    'Groups per Mentor': snapshot.groups,
    'Students per Mentor': snapshot.students,
    'Last Login': snapshot.lastLogin,
    Coverage: snapshot.coverage,
  })) {
    // Last Login comes from the mentor accounts, so it does not depend on the
    // message activity source.
    const missing = section === 'Background' ? available.background === false
      : section === 'Last Login' ? false
        : section !== 'Status' && !groupsAvailable
    if (missing) {
      rows.push([section, 'Availability', unknown, 'The data for this section could not be loaded.'])
      continue
    }
    const [base, baseLabel] = section === 'Capacity'
      ? [snapshot.capacityPool.activatedMentors, 'activated mentors']
      : [snapshot.total, 'mentors']
    for (const bucket of buckets)
      rows.push([
        section,
        bucket.label,
        bucket.value,
        `${percent(bucket.value, base)}% of ${baseLabel}`,
      ])
  }
  for (const point of activityAvailable ? activity.monthly : []) {
    rows.push([
      'Monthly Activity',
      point.month,
      point.active,
      'Distinct mentors with a login or message',
    ])
    rows.push(
      ['Monthly Messages', point.month, point.messages],
      ['Monthly Logins', point.month, point.logins],
    )
  }
  ;(activityAvailable ? activity.ranking : []).forEach((mentor, index) =>
    rows.push(['Mentor Activity', mentor.name, mentor.messages, `Rank ${index + 1}; messages in range`]),
  )
  if (groupsAvailable) {
    const pool = snapshot.capacityPool
    rows.push(
      ['Capacity Pool', 'Activated mentors', pool.activatedMentors, 'Accounts with status active'],
      ['Capacity Pool', 'Total group capacity', pool.totalSlots, 'Sum of activated mentors\' configured capacity'],
      ['Capacity Pool', 'Groups supported', pool.usedSlots, 'Current groups of activated mentors'],
      ['Capacity Pool', 'Open group slots', pool.openSlots, 'Capacity not yet used'],
      ['Capacity Pool', 'Utilisation (%)', pool.utilisation, 'Groups supported / total capacity'],
    )
  }
  if (!activityAvailable) rows.push(['Monthly Activity', 'Availability', unknown, 'Message activity could not be loaded.'])
  snapshot.insights.forEach((item) => {
    const missing = ['Unassigned mentors', 'Near capacity', 'Over capacity'].includes(item.label)
      ? !groupsAvailable
      : false
    rows.push(['Insight', item.label, missing ? unknown : item.value,
      missing ? 'The data for this metric could not be loaded.' : item.detail])
  })
  return (
    '\ufeff' +
    rows
      .map((row) =>
        Array.from({ length: 4 }, (_, index) => {
          let value = String(row[index] ?? '')
          if (/^[=+@\-\t\r]/.test(value)) value = `'${value}`
          return `"${value.replace(/"/g, '""')}"`
        }).join(','),
      )
      .join('\r\n')
  )
}
