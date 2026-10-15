import { BTF_COLORS } from '@/constants/btfTheme'
import { ANALYTICS_REFRESH_INTERVAL_MS } from '@/utils/analyticsRefresh'
import type {
  ActivityAnalyticsData,
  ActivityRole,
  ActivityStatus,
  AnalyticsYearData,
  DemoMentor,
  EmailLog,
  EmailMonitoringData,
  GroupsAnalyticsYear,
  MentorBackground,
  MentorEvent,
  MentorStatus,
  MessagesAnalyticsYear,
  RegistrationFollowUp,
  RegistrationTrendPoint,
  ResourceUsageItem,
  UserAnalyticsYear,
} from '@/types/analytics'
import {
  fetchAllGroups,
  fetchAllResources,
  fetchAllUsers,
  fetchGroupActivity,
  fetchLoginActivity,
  fetchEmailDeliveryAnalytics,
  fetchMentors,
  fetchResourceAnalytics,
  type AdminGroup,
  type AdminMentor,
  type AdminUser,
  type EmailDeliveryAnalyticsResponse,
  type GroupActivityResponse,
  type LoginActivityResponse,
  type ResourceAnalyticsResponse,
} from '@/utils/liveAnalyticsApi'

export type LiveBundle = {
  users: AdminUser[]
  groups: AdminGroup[]
  mentors: AdminMentor[]
  groupActivity: GroupActivityResponse
  loginActivity?: LoginActivityResponse
  resourceAnalytics: ResourceAnalyticsResponse
  emailAnalytics: EmailDeliveryAnalyticsResponse
  resources: Awaited<ReturnType<typeof fetchAllResources>>
}

export type ParticipantAnalyticsBundle = Pick<LiveBundle, 'users' | 'groupActivity' | 'loginActivity'>
export type CoreAnalyticsBundle = ParticipantAnalyticsBundle & Pick<LiveBundle, 'groups'>
export type MentorAnalyticsBundle = CoreAnalyticsBundle & Pick<LiveBundle, 'mentors'>
export type ResourceAnalyticsBundle = Pick<LiveBundle, 'resourceAnalytics' | 'resources'>
export type EmailAnalyticsBundle = ParticipantAnalyticsBundle & Pick<LiveBundle, 'emailAnalytics'>
export type OverviewAnalyticsBundle = CoreAnalyticsBundle & ResourceAnalyticsBundle & Pick<LiveBundle, 'emailAnalytics'> & {
  unavailableSources?: Array<'users' | 'groups' | 'groupActivity' | 'loginActivity' | 'resourceAnalytics' | 'emailAnalytics' | 'resources'>
}

export const ANALYTICS_CACHE_TTL_MS = ANALYTICS_REFRESH_INTERVAL_MS

function createCachedLoader<T>(fetcher: () => Promise<T>) {
  let cached: Promise<T> | null = null
  let expiresAt = 0
  const load = (force = false) => {
    if (!cached || force || Date.now() >= expiresAt) {
      expiresAt = Number.POSITIVE_INFINITY
      const request = fetcher()
      cached = request
      void request.then(() => {
        if (cached === request) expiresAt = Date.now() + ANALYTICS_CACHE_TTL_MS
      }, () => {})
      void request.catch(() => {
        if (cached === request) cached = null
      })
    }
    return cached
  }
  load.clear = () => { cached = null; expiresAt = 0 }
  return load
}

function emptyGroupActivity(): GroupActivityResponse {
  return {
    messages_by_group: [],
    messages_by_user: [],
    messages_by_day: [],
    messages_by_group_by_day: [],
    mentor_count: 0,
    student_count: 0,
    students_per_mentor: null,
    query_range: { start: null, end: null },
  }
}

// Cache complete page payloads instead of globally caching every raw source.
// This keeps navigation deduplicated while ensuring one page's refresh and
// data requirements cannot invalidate or expand another page's requests.
const usersPageLoader = createCachedLoader<ParticipantAnalyticsBundle>(async () => {
  const [users, loginActivity] = await Promise.all([fetchAllUsers(), fetchLoginActivity()])
  return { users, loginActivity, groupActivity: emptyGroupActivity() }
})

const registrationPageLoader = createCachedLoader<ParticipantAnalyticsBundle>(async () => ({
  users: await fetchAllUsers(),
  groupActivity: emptyGroupActivity(),
}))

const groupsPageLoader = createCachedLoader<CoreAnalyticsBundle>(async () => {
  const [users, groups, groupActivity] = await Promise.all([
    fetchAllUsers(), fetchAllGroups(), fetchGroupActivity(),
  ])
  return { users, groups, groupActivity }
})

const activityPageLoader = createCachedLoader<CoreAnalyticsBundle>(async () => {
  const [users, groups, groupActivity, loginActivity] = await Promise.all([
    fetchAllUsers(), fetchAllGroups(), fetchGroupActivity(), fetchLoginActivity(),
  ])
  return { users, groups, groupActivity, loginActivity }
})

const messagesPageLoader = createCachedLoader<CoreAnalyticsBundle>(async () => {
  const [users, groups, groupActivity] = await Promise.all([
    fetchAllUsers(), fetchAllGroups(), fetchGroupActivity(),
  ])
  return { users, groups, groupActivity }
})

const mentorsPageLoader = createCachedLoader<MentorAnalyticsBundle>(async () => {
  const [users, groups, mentors, groupActivity] = await Promise.all([
    fetchAllUsers(), fetchAllGroups(), fetchMentors(), fetchGroupActivity(),
  ])
  return { users, groups, mentors, groupActivity }
})

const resourcesPageLoader = createCachedLoader<ResourceAnalyticsBundle>(async () => {
  const [resourceAnalytics, resources] = await Promise.all([
    fetchResourceAnalytics(), fetchAllResources(),
  ])
  return { resourceAnalytics, resources }
})

const emailPageLoader = createCachedLoader<EmailAnalyticsBundle>(async () => ({
  users: [],
  groupActivity: emptyGroupActivity(),
  emailAnalytics: await fetchEmailDeliveryAnalytics(),
}))

const overviewPageLoader = createCachedLoader<OverviewAnalyticsBundle>(async () => {
  const sources = ['users', 'groups', 'groupActivity', 'loginActivity', 'resourceAnalytics', 'emailAnalytics', 'resources'] as const
  const results = await Promise.allSettled([
    fetchAllUsers(),
    fetchAllGroups(),
    fetchGroupActivity(),
    fetchLoginActivity(),
    fetchResourceAnalytics(),
    fetchEmailDeliveryAnalytics(),
    fetchAllResources(),
  ])
  const unavailableSources = sources.filter((_, index) => results[index]?.status === 'rejected')
  if (unavailableSources.length === sources.length) throw new Error('All analytics data sources are unavailable.')
  const value = <T>(index: number, fallback: T): T => {
    const result = results[index]
    return result?.status === 'fulfilled' ? result.value as T : fallback
  }
  return {
    users: value<AdminUser[]>(0, []), groups: value<AdminGroup[]>(1, []),
    groupActivity: value(2, emptyGroupActivity()), loginActivity: value<LoginActivityResponse | undefined>(3, undefined),
    resourceAnalytics: value<ResourceAnalyticsResponse>(4, {
      total_clicks: 0, unique_users: 0, active_resources: 0,
      clicks_by_day: [], top_resources: [], clicks_by_category: [], query_range: { start: null, end: null },
    }),
    emailAnalytics: value<EmailDeliveryAnalyticsResponse>(5, {
      snapshot_at: null, mailboxes: [], totals: { attempted: 0, delivered: 0, failed: 0, delivery_runs: 0 },
      hourly: [], daily: [], recent_deliveries: [],
    }),
    resources: value(6, []), unavailableSources,
  }
})

export const loadUsersAnalyticsBundle = (force = false) => usersPageLoader(force)
export const loadRegistrationAnalyticsBundle = (force = false) => registrationPageLoader(force)
export const loadGroupsAnalyticsBundle = (force = false) => groupsPageLoader(force)
export const loadActivityAnalyticsBundle = (force = false) => activityPageLoader(force)
export const loadMessagesAnalyticsBundle = (force = false) => messagesPageLoader(force)
export const loadMentorsAnalyticsBundle = (force = false) => mentorsPageLoader(force)
export const loadResourcesAnalyticsBundle = (force = false) => resourcesPageLoader(force)
export const loadEmailMonitoringAnalyticsBundle = (force = false) => emailPageLoader(force)
export const loadOverviewAnalyticsBundle = (force = false) => overviewPageLoader(force)

export const clearUsersAnalyticsCache = () => usersPageLoader.clear()
export const clearRegistrationAnalyticsCache = () => registrationPageLoader.clear()
export const clearGroupsAnalyticsCache = () => groupsPageLoader.clear()
export const clearActivityAnalyticsCache = () => activityPageLoader.clear()
export const clearMessagesAnalyticsCache = () => messagesPageLoader.clear()
export const clearMentorsAnalyticsCache = () => mentorsPageLoader.clear()
export const clearResourcesAnalyticsCache = () => resourcesPageLoader.clear()
export const clearEmailMonitoringAnalyticsCache = () => emailPageLoader.clear()
export const clearOverviewAnalyticsCache = () => overviewPageLoader.clear()

// Backwards-compatible exports for callers outside the analytics pages.
export const loadParticipantAnalyticsBundle = loadUsersAnalyticsBundle
export const loadCoreAnalyticsBundle = loadActivityAnalyticsBundle
export const loadMentorAnalyticsBundle = loadMentorsAnalyticsBundle
export const loadResourceAnalyticsBundle = loadResourcesAnalyticsBundle
export const loadEmailAnalyticsBundle = loadEmailMonitoringAnalyticsBundle

export function clearLiveAnalyticsCache() {
  for (const loader of [
    usersPageLoader,
    registrationPageLoader,
    groupsPageLoader,
    activityPageLoader,
    messagesPageLoader,
    mentorsPageLoader,
    resourcesPageLoader,
    emailPageLoader,
    overviewPageLoader,
  ]) loader.clear()
}

const roleTitle = (role: string | null): ActivityRole | null => {
  const value = (role ?? '').toLowerCase()
  if (value === 'student') return 'Student'
  if (value === 'mentor') return 'Mentor'
  if (value === 'supervisor') return 'Supervisor'
  return null
}

const isoDay = (value: string | null | undefined) => value?.slice(0, 10) ?? ''

function safeDate(value: string | null | undefined) {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

function latestObservedDate(
  users: AdminUser[],
  activity?: GroupActivityResponse,
  loginActivity?: LoginActivityResponse,
) {
  const values: Date[] = []
  for (const user of users) {
    const date = safeDate(user.lastLogin ?? user.activatedAt ?? user.invitedAt)
    if (date) values.push(date)
  }
  for (const row of activity?.messages_by_day ?? []) {
    const date = safeDate(row.date)
    if (date) values.push(date)
  }
  const latestLoginActivity = safeDate(loginActivity?.latest_activity_date)
  if (latestLoginActivity) values.push(latestLoginActivity)
  if (!values.length) return new Date()
  return new Date(Math.max(...values.map((date) => date.getTime())))
}

export function liveAnalyticsYear(bundle: Pick<LiveBundle, 'users' | 'groupActivity' | 'loginActivity'>) {
  return latestObservedDate(bundle.users, bundle.groupActivity, bundle.loginActivity).getUTCFullYear()
}

export function liveAnalyticsAsOf(bundle: Pick<LiveBundle, 'users' | 'groupActivity' | 'loginActivity'>) {
  return latestObservedDate(bundle.users, bundle.groupActivity, bundle.loginActivity).toISOString().slice(0, 10)
}

function daysBetween(date: Date, asOf: Date) {
  return Math.max(0, Math.floor((asOf.getTime() - date.getTime()) / 86_400_000))
}

function loginStatus(user: AdminUser, asOf: Date): ActivityStatus {
  const last = safeDate(user.lastLogin)
  if (!last) return 'Never'
  // Activity status describes login recency only. Account lifecycle state
  // (active, invited, suspended, etc.) is a separate concern and must not
  // make two users with the same login recency show different statuses.
  return daysBetween(last, asOf) < 7 ? 'Active' : 'Inactive'
}

function roleUsers(users: AdminUser[]) {
  return users.filter((user) => !user.isAdmin && roleTitle(user.role))
}

function percent(value: number, total: number) {
  return total ? Math.round((value / total) * 100) : 0
}

function registrationDate(user: AdminUser) {
  return safeDate(user.createdAt ?? user.invitedAt ?? user.activatedAt)
}

function monthlyCumulative(users: AdminUser[], role: ActivityRole, year: number) {
  const result = Array.from({ length: 12 }, () => 0)
  for (const user of users) {
    if (roleTitle(user.role) !== role) continue
    const joined = registrationDate(user)
    if (!joined || joined.getUTCFullYear() !== year) continue
    for (let month = joined.getUTCMonth(); month < 12; month += 1) result[month] += 1
  }
  return result
}

export function buildUsersAnalytics(bundle: ParticipantAnalyticsBundle): UserAnalyticsYear {
  const users = roleUsers(bundle.users)
  const asOf = safeDate(bundle.loginActivity?.latest_activity_date)
    ?? latestObservedDate(users, bundle.groupActivity, bundle.loginActivity)
  const year = new Date().getUTCFullYear()
  const students = users.filter((user) => roleTitle(user.role) === 'Student')
  const mentors = users.filter((user) => roleTitle(user.role) === 'Mentor')
  const supervisors = users.filter((user) => roleTitle(user.role) === 'Supervisor')

  // For the current year, last_login preserves whether each current user has
  // logged in this year, including logins before audit tracking was deployed.
  const loggedInThisYear = (rows: AdminUser[]) => rows.filter((user) =>
    safeDate(user.lastLogin)?.getUTCFullYear() === year,
  ).length
  const loginCountByRole: Record<ActivityRole, number> = {
    Student: loggedInThisYear(students), Mentor: loggedInThisYear(mentors), Supervisor: loggedInThisYear(supervisors),
  }
  const rate = (role: ActivityRole, rows: AdminUser[]) => percent(loginCountByRole[role], rows.length)
  const recency = [
    { label: '< 7 days', min: 0, max: 6 },
    { label: '7–14 days', min: 7, max: 14 },
    { label: '15–30 days', min: 15, max: 30 },
    { label: '31–90 days', min: 31, max: 90 },
    { label: '> 90 days', min: 91, max: Number.POSITIVE_INFINITY },
  ].map((bucket) => ({
    label: bucket.label,
    value: users.filter((user) => {
      const last = safeDate(user.lastLogin)
      if (!last) return false
      const days = daysBetween(last, asOf)
      return days >= bucket.min && days <= bucket.max
    }).length,
  }))
  recency.push({ label: 'Never', value: users.filter((user) => !user.lastLogin).length })

  const regionsMap = new Map<string, number>()
  const interestMap = new Map<string, { students: number; mentors: number }>()
  for (const user of users) {
    const region = user.state?.stateName || user.country?.countryName || 'Unknown'
    regionsMap.set(region, (regionsMap.get(region) ?? 0) + 1)
    for (const interest of user.interests ?? []) {
      const item = interestMap.get(interest) ?? { students: 0, mentors: 0 }
      if (roleTitle(user.role) === 'Student') item.students += 1
      if (roleTitle(user.role) === 'Mentor') item.mentors += 1
      interestMap.set(interest, item)
    }
  }

  const dailyLabels: string[] = []
  const dailyTotal: number[] = []
  const loginByDay = new Map(bundle.loginActivity?.by_day.map((row) => [row.date, row.total]) ?? [])
  for (let offset = 9; offset >= 0; offset -= 1) {
    const day = new Date(asOf)
    day.setUTCDate(asOf.getUTCDate() - offset)
    const key = day.toISOString().slice(0, 10)
    dailyLabels.push(day.toLocaleDateString('en-AU', { day: '2-digit', month: 'short', timeZone: 'UTC' }))
    dailyTotal.push(
      bundle.loginActivity
        ? loginByDay.get(key) ?? 0
        : users.filter((user) => isoDay(user.lastLogin) === key).length,
    )
  }

  return {
    totalUsers: users.length,
    students: students.length,
    mentors: mentors.length,
    supervisors: supervisors.length,
    totalGrowth: null,
    studentGrowth: null,
    mentorGrowth: null,
    supervisorGrowth: null,
    loginRates: {
      students: rate('Student', students),
      mentors: rate('Mentor', mentors),
      supervisors: rate('Supervisor', supervisors),
    },
    dailyActivity: { labels: dailyLabels, total: dailyTotal },
    lastLogin: recency,
    userLastLogins: users.map((user) => {
      const activityStatus = loginStatus(user, asOf)
      const lastLoginDate = safeDate(user.lastLogin)
      const status: 'Recent' | 'Inactive' | 'Never' =
        activityStatus === 'Active' ? 'Recent' : activityStatus

      return {
        id: user.id,
        name: `${user.firstName} ${user.lastName}`.trim() || user.email,
        role: roleTitle(user.role)!,
        lastLoginIso: lastLoginDate ? user.lastLogin : null,
        daysInactive: lastLoginDate ? daysBetween(lastLoginDate, asOf) : null,
        lastLogin: lastLoginDate
          ? lastLoginDate.toLocaleString('en-AU', {
              dateStyle: 'medium',
              timeStyle: 'short',
              timeZone: 'UTC',
            })
          : 'Never',
        status,
      }
    }),
    registration: {
      students: monthlyCumulative(users, 'Student', year),
      mentors: monthlyCumulative(users, 'Mentor', year),
      supervisors: monthlyCumulative(users, 'Supervisor', year),
    },
    regions: [...regionsMap.entries()].map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value),
    interests: [...interestMap.entries()]
      .map(([name, counts]) => ({ name, ...counts }))
      .sort((a, b) => b.students + b.mentors - (a.students + a.mentors)),
  }
}

export function buildActivityAnalytics(bundle: CoreAnalyticsBundle): ActivityAnalyticsData {
  const users = roleUsers(bundle.users)
  const asOf = safeDate(bundle.loginActivity?.latest_activity_date)
    ?? latestObservedDate(users, bundle.groupActivity, bundle.loginActivity)
  const rows = users.map((user) => {
    const role = roleTitle(user.role)!
    const last = safeDate(user.lastLogin)
    const daysInactive = last ? daysBetween(last, asOf) : null
    const status = loginStatus(user, asOf)
    return {
      id: user.id,
      name: `${user.firstName} ${user.lastName}`.trim() || user.email,
      role,
      lastLogin: user.lastLogin,
      daysInactive,
      daysActive: status === 'Active' && daysInactive !== null ? Math.max(1, 8 - daysInactive) : null,
      status,
      isActive: user.isActive,
      accountStatus: user.accountStatus,
    }
  })

  const within = (days: number) => rows.filter((row) => row.daysInactive !== null && row.daysInactive < days).length
  const never = rows.filter((row) => row.status === 'Never').length
  const loginHistoryAvailable = !!bundle.loginActivity?.by_day.length
  const activityYear = asOf.getUTCFullYear()
  const yearlyLogins = bundle.loginActivity?.by_year.find((row) => row.year === activityYear)
  const rates = (['Student', 'Mentor', 'Supervisor'] as ActivityRole[]).map((role) => {
    const roleRows = rows.filter((row) => row.role === role)
    const recorded = role === 'Student'
      ? yearlyLogins?.students
      : role === 'Mentor'
        ? yearlyLogins?.mentors
        : yearlyLogins?.supervisors
    return {
      role,
      value: percent(
        recorded ?? roleRows.filter((row) => row.status !== 'Never').length,
        roleRows.length,
      ),
    }
  })

  const dailySeries = { students: [] as number[], mentors: [] as number[], supervisors: [] as number[] }
  const loginByDay = new Map(bundle.loginActivity?.by_day.map((row) => [row.date, row]) ?? [])
  for (let offset = 6; offset >= 0; offset -= 1) {
    const day = new Date(asOf)
    day.setUTCDate(asOf.getUTCDate() - offset)
    const key = day.toISOString().slice(0, 10)
    const recorded = loginByDay.get(key)
    dailySeries.students.push(recorded?.students ?? (bundle.loginActivity ? 0 : rows.filter((row) => row.role === 'Student' && isoDay(row.lastLogin) === key).length))
    dailySeries.mentors.push(recorded?.mentors ?? (bundle.loginActivity ? 0 : rows.filter((row) => row.role === 'Mentor' && isoDay(row.lastLogin) === key).length))
    dailySeries.supervisors.push(recorded?.supervisors ?? (bundle.loginActivity ? 0 : rows.filter((row) => row.role === 'Supervisor' && isoDay(row.lastLogin) === key).length))
  }

  const bucket = (min: number, max: number) => rows.filter((row) => row.daysInactive !== null && row.daysInactive >= min && row.daysInactive <= max).length
  return {
    totalUsers: rows.length,
    dailyActive: loginHistoryAvailable ? bundle.loginActivity!.active_users.daily : null,
    weeklyActive: loginHistoryAvailable ? bundle.loginActivity!.active_users.weekly : null,
    monthlyActive: loginHistoryAvailable ? bundle.loginActivity!.active_users.monthly : null,
    loggedInRate: percent(rows.length - never, rows.length),
    neverLoggedIn: never,
    loginHistoryAvailable,
    dailySeries: loginHistoryAvailable ? dailySeries : { students: [], mentors: [], supervisors: [] },
    roleLoginRates: rates,
    loginRecency: [
      { label: 'Today', value: within(1) },
      { label: 'Last 7 days', value: bucket(1, 7) },
      { label: '8–14 days', value: bucket(8, 14) },
      { label: '15–30 days', value: bucket(15, 30) },
      { label: '31–90 days', value: bucket(31, 90) },
      { label: '> 90 days', value: rows.filter((row) => (row.daysInactive ?? 0) > 90).length },
      { label: 'Never', value: never },
    ],
    users: rows,
  }
}

export function buildRegistrationAnalytics(bundle: ParticipantAnalyticsBundle) {
  const users = roleUsers(bundle.users)
  const asOf = latestObservedDate(users, bundle.groupActivity)
  const students = users.filter((user) => roleTitle(user.role) === 'Student')
  const mentors = users.filter((user) => roleTitle(user.role) === 'Mentor')

  const dates = new Map<string, { students: number; mentors: number }>()
  for (const user of [...students, ...mentors]) {
    const joined = registrationDate(user)
    if (!joined) continue
    const key = joined.toISOString().slice(0, 10)
    const row = dates.get(key) ?? { students: 0, mentors: 0 }
    if (roleTitle(user.role) === 'Student') row.students += 1
    if (roleTitle(user.role) === 'Mentor') row.mentors += 1
    dates.set(key, row)
  }
  const trend: RegistrationTrendPoint[] = [...dates.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, row]) => ({ date, ...row }))

  const followUps: RegistrationFollowUp[] = []
  for (const user of students) {
    const registered = registrationDate(user) ?? asOf
    const base = {
      id: user.id,
      student: `${user.firstName} ${user.lastName}`.trim() || user.email,
      email: user.email,
      supervisor: user.supervisorName || '—',
      registrationDate: registered.toISOString().slice(0, 10),
      daysOutstanding: daysBetween(registered, asOf),
      // Registration source is not persisted by the current schema. Keep the
      // missing value explicit instead of assigning every student to a fake
      // "Individual" source.
      source: null,
    }
    if (!user.guardianEmail) {
      followUps.push({ ...base, issue: 'missing_guardian' })
    } else if (!user.joinPermissionReceived) {
      followUps.push({ ...base, issue: 'awaiting_approval' })
    }
  }

  return {
    trend,
    completion: {
      registered: students.length,
      guardianDetails: students.filter((user) => !!user.guardianEmail).length,
      guardianApproved: students.filter(
        (user) => !!user.guardianEmail && user.joinPermissionReceived,
      ).length,
    },
    sources: [],
    followUps,
  }
}

function groupBucket(size: number) {
  if (size === 0) return '0'
  if (size <= 2) return '1–2'
  if (size <= 4) return '3–4'
  if (size <= 6) return '5–6'
  if (size <= 8) return '7–8'
  if (size <= 10) return '9–10'
  if (size <= 12) return '11–12'
  if (size <= 14) return '13–14'
  return '15+'
}

function groupMentors(group: AdminGroup) {
  if (group.mentors) return group.mentors
  return group.mentor ? [group.mentor] : []
}

export function analyticsYears(bundle: Pick<LiveBundle, 'users' | 'groupActivity' | 'loginActivity'>) {
  const years = new Set<number>()
  for (const row of bundle.groupActivity.messages_by_day) years.add(Number(row.date.slice(0, 4)))
  for (const row of bundle.loginActivity?.by_day ?? []) years.add(Number(row.date.slice(0, 4)))
  for (const user of bundle.users) {
    const date = safeDate(user.activatedAt ?? user.invitedAt)
    if (date) years.add(date.getUTCFullYear())
  }
  if (!years.size) years.add(new Date().getUTCFullYear())
  return [...years].sort((a, b) => b - a)
}

export function buildGroupsAnalytics(
  bundle: CoreAnalyticsBundle,
  activityYear = liveAnalyticsYear(bundle),
): GroupsAnalyticsYear {
  const groups = bundle.groups
  const groupMessages = new Map(bundle.groupActivity.messages_by_group.map((row) => [String(row.group_id), row.message_count]))
  const sizes = groups.map((group) => group.members.filter((member) => member.role.toLowerCase() === 'student').length)
  const withMentor = groups.filter((group) => groupMentors(group).length > 0).length
  const totalStudents = sizes.reduce((sum, value) => sum + value, 0)
  const buckets = ['0', '1–2', '3–4', '5–6', '7–8', '9–10', '11–12', '13–14', '15+']
  const groupSizeDistribution = buckets.map((label) => ({ label, value: 0 }))
  for (const size of sizes) {
    const item = groupSizeDistribution.find((row) => row.label === groupBucket(size))
    if (item) item.value += 1
  }

  const ratioMap = new Map<string, number>()
  for (const group of groups) {
    const size = new Set(group.members.filter((m) => m.role.toLowerCase() === 'student').map((m) => m.id)).size
    const mentorIds = new Set(groupMentors(group).map((mentor) => mentor.id))
    const perMentor = mentorIds.size ? size / mentorIds.size : null
    const label = perMentor === null ? 'No mentor' : perMentor >= 12 ? '1:12+' : `1:${Number(perMentor.toFixed(2))}`
    ratioMap.set(label, (ratioMap.get(label) ?? 0) + 1)
  }

  const recentEnd = liveAnalyticsAsOf(bundle)
  const recentStartDate = new Date(`${recentEnd}T00:00:00Z`)
  recentStartDate.setUTCDate(recentStartDate.getUTCDate() - 6)
  const recentStart = recentStartDate.toISOString().slice(0, 10)
  const recentGroupIds = new Set(
    bundle.groupActivity.messages_by_group_by_day
      .filter((row) => row.date >= recentStart && row.date <= recentEnd && row.message_count > 0)
      .map((row) => String(row.group_id)),
  )
  const active = groups.filter((group) => recentGroupIds.has(String(group.id))).length
  const notStarted = groups.filter(
    (group) => (groupMessages.get(String(group.id)) ?? 0) === 0 && group.members.length === 0,
  ).length
  const inactive = Math.max(0, groups.length - active - notStarted)

  return {
    totalGroups: groups.length,
    groupGrowth: null,
    averageGroupSize: groups.length ? Number((totalStudents / groups.length).toFixed(1)) : 0,
    avgSizeChange: null,
    groupsWithMentor: withMentor,
    groupsWithoutMentor: groups.length - withMentor,
    mentorStudentRatio: bundle.groupActivity.students_per_mentor,
    smallGroups: sizes.filter((size) => size < 3).length,
    inactiveRecent: inactive + notStarted,
    nearCapacity: sizes.filter((size) => size >= 10).length,
    groupSizeDistribution,
    groupStatus: [
      { label: 'Active', value: active, color: BTF_COLORS.darkGreen },
      { label: 'Inactive', value: inactive, color: BTF_COLORS.mintGreen },
      { label: 'Not started', value: notStarted, color: BTF_COLORS.lightGreen },
    ],
    ratioDistribution: [...ratioMap.entries()].map(([label, value]) => ({ label, value })),
    groupActivity: Array.from({ length: 12 }, (_, month) => {
      const activeGroupIds = new Set(
        bundle.groupActivity.messages_by_group_by_day
          .filter((row) => new Date(row.date).getUTCFullYear() === activityYear && new Date(row.date).getUTCMonth() === month && row.message_count > 0)
          .map((row) => String(row.group_id)),
      )
      return {
        month: new Date(Date.UTC(2000, month, 1)).toLocaleDateString('en-AU', { month: 'short', timeZone: 'UTC' }),
        active: activeGroupIds.size,
        inactive: Math.max(0, groups.length - activeGroupIds.size),
      }
    }),
  }
}

export function buildMessagesAnalytics(bundle: CoreAnalyticsBundle): MessagesAnalyticsYear {
  const end = bundle.groupActivity.query_range.end ?? liveAnalyticsAsOf(bundle)
  const anchor = new Date(`${end}T00:00:00Z`)
  const year = anchor.getUTCFullYear()
  const groups = bundle.groupActivity.messages_by_group
  const usersById = new Map(bundle.users.map((user) => [user.id, user]))
  const users = bundle.groupActivity.messages_by_user.map((row) => ({
    id: row.user_id,
    name: row.name,
    value: row.message_count,
    role: roleTitle(usersById.get(row.user_id)?.role ?? null) ?? 'Unavailable',
  }))
  const byMonth = Array.from({ length: 12 }, () => 0)
  for (const row of bundle.groupActivity.messages_by_day) {
    if (new Date(row.date).getUTCFullYear() !== year) continue
    const month = new Date(row.date).getUTCMonth()
    byMonth[month] += row.message_count
  }
  const daily = new Map(bundle.groupActivity.messages_by_day.map((row) => [row.date, row.message_count]))
  const weekly = Array.from({ length: 7 }, (_, i) => {
    const date = new Date(anchor)
    date.setUTCDate(date.getUTCDate() - 6 + i)
    return daily.get(date.toISOString().slice(0, 10)) ?? 0
  })
  const monthWeeks = [0, 0, 0, 0, 0]
  for (const row of bundle.groupActivity.messages_by_day) {
    const date = new Date(row.date)
    if (date.getUTCFullYear() !== year || date.getUTCMonth() !== anchor.getUTCMonth()) continue
    const index = Math.min(4, Math.floor((date.getUTCDate() - 1) / 7))
    monthWeeks[index] += row.message_count
  }
  return {
    totalMessages: groups.reduce((sum, row) => sum + row.message_count, 0),
    totalGroups: groups.length,
    groupsWithMessages: groups.filter((row) => row.message_count > 0).length,
    groups: groups.map((row) => ({ id: row.group_id, name: row.group_name, value: row.message_count })).sort((a, b) => b.value - a.value),
    users: users.sort((a, b) => b.value - a.value),
    monthly: byMonth,
    weekly,
    monthWeeks,
  }
}

export function buildResourcesAnalytics(bundle: ResourceAnalyticsBundle) {
  const analytics = bundle.resourceAnalytics
  const resourceMeta = new Map(
    bundle.resources.flatMap((resource) => {
      const id = resource.resource_id ?? resource.id
      return typeof id === 'number' ? [[id, resource] as const] : []
    }),
  )
  // Keep recorded rows authoritative; supplement only catalogue IDs without activity.
  const recordedIds = new Set(analytics.top_resources.map((row) => row.resource_id))
  const resourceRows = [
    ...analytics.top_resources,
    ...[...resourceMeta.entries()]
      .filter(([id]) => !recordedIds.has(id))
      .map(([id, resource]) => ({
        resource_id: id,
        resource_name: resource.resource_name,
        click_count: 0,
        unique_users: 0,
      })),
  ]
  const resources: ResourceUsageItem[] = resourceRows.map((row) => {
    const meta = resourceMeta.get(row.resource_id)
    const roles = (meta?.audiences ?? [])
      .map((audience) => audience.role?.slug ?? audience.role?.role_name ?? '')
      .map((role) => role.toLowerCase())
      .filter((role) => ['student', 'mentor', 'supervisor'].includes(role))
      .map((role) => (role[0].toUpperCase() + role.slice(1)) as 'Student' | 'Mentor' | 'Supervisor')
    return {
      id: row.resource_id,
      name: row.resource_name,
      clicks: row.click_count,
      uniqueUsers: row.unique_users,
      type: meta?.resource_type ?? 'Uncategorised',
      roles,
    }
  })
  return {
    totalClicks: analytics.total_clicks,
    uniqueUsers: analytics.unique_users,
    activeResources: analytics.active_resources,
    mostUsedResource: analytics.top_resources[0]?.resource_name ?? '—',
    dailyClicks: analytics.clicks_by_day.map((row) => ({ label: row.date, clicks: row.click_count })),
    resources,
    byType: analytics.clicks_by_category.map((row, index) => ({
      label: row.category_name ?? 'Uncategorised',
      value: row.click_count,
      color: [BTF_COLORS.darkGreen, BTF_COLORS.airForceBlue, BTF_COLORS.mintGreen, BTF_COLORS.lightGreen][index % 4],
    })),
  }
}

export function buildMentorData(bundle: MentorAnalyticsBundle) {
  const groupsByMentor = new Map<string, AdminGroup[]>()
  for (const group of bundle.groups) {
    for (const mentor of groupMentors(group)) {
      const rows = groupsByMentor.get(mentor.id) ?? []
      rows.push(group)
      groupsByMentor.set(mentor.id, rows)
    }
  }

  const mentors: DemoMentor[] = bundle.mentors.map((mentor) => {
    const groups = groupsByMentor.get(String(mentor.mentorId)) ?? []
    const studentIds = groups.flatMap((group) =>
      group.members.filter((member) => member.role.toLowerCase() === 'student').map((member) => member.id),
    )
    const status: MentorStatus = mentor.isActive ? 'active' : mentor.hasLoggedIn ? 'inactive' : 'onboarding'
    const rawBackground = bundle.users.find((user) => user.id === mentor.mentorId)?.mentorBackground
    const allowed: MentorBackground[] = ['industry', 'undergraduate', 'postgraduate', 'hdr']
    const background = allowed.includes(rawBackground as MentorBackground)
      ? (rawBackground as MentorBackground)
      : 'unknown'
    return {
      id: String(mentor.mentorId),
      name: mentor.name,
      status,
      background,
      capacity: mentor.maxGroupCount ?? 0,
      groupIds: groups.map((group) => group.id),
      studentIds: [...new Set(studentIds)],
    }
  })

  const events: MentorEvent[] = (bundle.groupActivity.mentor_activity_by_day ?? [])
    .map((event) => ({
      mentorId: String(event.mentor_id),
      date: event.date,
      logins: event.logins,
      messages: event.messages,
    }))
  const snapshotDate = events.reduce(
    (latest, event) => event.date > latest ? event.date : latest,
    latestObservedDate(bundle.users, bundle.groupActivity).toISOString().slice(0, 10),
  )
  return { mentors, events, snapshotDate }
}


export function buildEmailMonitoring(bundle: EmailAnalyticsBundle): EmailMonitoringData {
  const email = bundle.emailAnalytics

  const fallbackQuota = email.quota_limit ?? 3000
  const mailboxRows = email.mailboxes?.length
    ? email.mailboxes
    : [{
        email: email.mailbox ?? 'info@biotechfutures.org',
        quota_limit: fallbackQuota,
        totals: email.totals,
        hourly: email.hourly,
        daily: email.daily,
      }]

  const infoMailbox =
    mailboxRows.find((mailbox) => mailbox.email.toLowerCase() === 'info@biotechfutures.org')
    ?? mailboxRows[0]

  const connectMailbox =
    mailboxRows.find((mailbox) => mailbox.email.toLowerCase() === 'connect@biotechfutures.org')
    ?? {
      email: 'connect@biotechfutures.org',
      quota_limit: fallbackQuota,
      totals: { attempted: 0, delivered: 0, failed: 0, delivery_runs: 0 },
      hourly: [],
      daily: [],
    }

  const hourlyMapFor = (mailbox: typeof infoMailbox) => {
    const map = new Map<string, { attempted: number; delivered: number; failed: number }>()
    for (const row of mailbox.hourly) {
      const parsed = safeDate(row.hour)
      if (!parsed) continue
      parsed.setUTCMinutes(0, 0, 0)
      const hour = parsed.toISOString()
      const existing = map.get(hour) ?? { attempted: 0, delivered: 0, failed: 0 }
      map.set(hour, {
        attempted: existing.attempted + row.attempted,
        delivered: existing.delivered + row.delivered,
        failed: existing.failed + row.failed,
      })
    }
    return map
  }

  const infoHourly = hourlyMapFor(infoMailbox)
  const connectHourly = hourlyMapFor(connectMailbox)

  const hourlyUsage = [...new Set([...infoHourly.keys(), ...connectHourly.keys()])]
    .sort((left, right) => left.localeCompare(right))
    .map((hour) => ({
      label: `${hour.slice(0, 13).replace('T', ' ')}:00 UTC`,
      info: infoHourly.get(hour)?.attempted ?? 0,
      connect: connectHourly.get(hour)?.attempted ?? 0,
    }))

  const peak = hourlyUsage.reduce<(typeof hourlyUsage)[number] | null>(
    (best, row) => !best || row.info + row.connect > best.info + best.connect ? row : best,
    null,
  )
  const latestRecordedHour = hourlyUsage[hourlyUsage.length - 1]
  const sentLastHour = latestRecordedHour
    ? latestRecordedHour.info + latestRecordedHour.connect
    : 0

  const combinedDailyMap = new Map<string, number>()
  for (const mailbox of mailboxRows) {
    for (const row of mailbox.daily) {
      combinedDailyMap.set(row.date, (combinedDailyMap.get(row.date) ?? 0) + row.attempted)
    }
  }
  const daily = [...combinedDailyMap.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, value]) => ({
      label: new Date(`${date}T00:00:00Z`).toLocaleDateString('en-AU', {
        day: '2-digit',
        month: 'short',
        timeZone: 'UTC',
      }),
      value,
    }))

  const totalDeliveryRuns = email.totals.delivery_runs
  const maxMailboxQuota = Math.max(...mailboxRows.map((mailbox) => mailbox.quota_limit), fallbackQuota)
  const roleStatusRows = email.status_by_role ?? []
  const roleAttribution = email.role_attribution ?? {
    basis: 'current_single_role_audience' as const,
    available: false,
    complete: false,
    tracked_delivery_runs: 0,
    unattributed_delivery_runs: email.totals.delivery_runs,
    tracked_attempted: 0,
    unattributed_attempted: email.totals.attempted,
    tracked_delivered: 0,
    unattributed_delivered: email.totals.delivered,
    tracked_failed: 0,
    unattributed_failed: email.totals.failed,
  }
  const trackedRoleDelivered = roleStatusRows.reduce((sum, row) => sum + row.delivered, 0)
  const trackedRoleFailed = roleStatusRows.reduce((sum, row) => sum + row.failed, 0)

  return {
    mailboxes: mailboxRows.map((mailbox) => ({
      email: mailbox.email,
      currentUsage: mailbox.totals.attempted,
      quotaLimit: mailbox.quota_limit,
    })),
    sentLastHour,
    peakHourLabel: peak?.label ?? '—',
    peakHourValue: peak ? peak.info + peak.connect : 0,
    hourlyUsage,
    verificationDaily: daily,
    verificationDailyBaseLimit: maxMailboxQuota,
    statusByRole: roleStatusRows.map((row) => ({
      role:
        row.role === 'Student'
          ? 'Students'
          : row.role === 'Mentor'
            ? 'Mentors'
            : 'Supervisors',
      attempted: row.attempted,
      delivered: row.delivered,
      opened: row.opened,
      failed: row.failed,
      trackedDeliveries: row.tracked_deliveries,
    })),
    roleAttribution: {
      basis: roleAttribution.basis,
      available: roleAttribution.available,
      complete: roleAttribution.complete,
      trackedDeliveryRuns: roleAttribution.tracked_delivery_runs,
      unattributedDeliveryRuns: roleAttribution.unattributed_delivery_runs,
      trackedAttempted: roleAttribution.tracked_attempted,
      unattributedAttempted: roleAttribution.unattributed_attempted,
      trackedDelivered: roleAttribution.tracked_delivered ?? trackedRoleDelivered,
      unattributedDelivered:
        roleAttribution.unattributed_delivered
        ?? Math.max(email.totals.delivered - trackedRoleDelivered, 0),
      trackedFailed: roleAttribution.tracked_failed ?? trackedRoleFailed,
      unattributedFailed:
        roleAttribution.unattributed_failed
        ?? Math.max(email.totals.failed - trackedRoleFailed, 0),
    },
    categories: [
      { label: 'All tracked email', value: email.totals.attempted, color: BTF_COLORS.darkGreen },
    ],
    alerts: mailboxRows
      .filter((mailbox) => mailbox.totals.attempted >= mailbox.quota_limit * 0.8)
      .map((mailbox, index) => ({
        id: index + 1,
        time: email.snapshot_at ?? '',
        type: 'Mailbox usage',
        detail: `${mailbox.email} has used ${mailbox.totals.attempted.toLocaleString()} of ${mailbox.quota_limit.toLocaleString()} messages in the rolling 24-hour window.`,
        status: 'Monitoring',
      })),
    overallStats: {
      delivered: email.totals.delivered,
      sent: email.totals.attempted,
      failed: email.totals.failed,
      // The current delivery schema records attempts, successes and failures
      // only. Engagement/provider metrics must remain unavailable
      // until an authorised event source is connected.
      clicked: null,
      opened: null,
      spam: null,
      averageSentPerUser: totalDeliveryRuns
        ? Number((email.totals.attempted / totalDeliveryRuns).toFixed(1))
        : null,
      averageOpenedPerUser: null,
      averageClickedPerUser: null,
    },
    logs: email.recent_deliveries.map((row) => {
      const status: EmailLog['status'] =
        row.status === 'partial' || (row.success_count > 0 && row.failure_count > 0)
          ? 'Partial'
          : row.status === 'failed' || (row.failure_count > 0 && row.success_count === 0)
            ? 'Failed'
            : 'Delivered'

      return {
        id: row.id,
        sender: row.initiated_by_name || 'System',
        senderEmail: row.initiated_by_email || '—',
        recipient: `Announcement audience (${row.recipient_count})`,
        recipientEmail: '—',
        title: row.title,
        sentAt: new Date(row.started_at).toLocaleString('en-AU', {
          dateStyle: 'medium',
          timeStyle: 'short',
        }),
        status,
      }
    }),
  }
}

function registrationsByRecentPeriods(users: AdminUser[], asOf: Date) {
  const participantUsers = roleUsers(users)
  const windows = [7, 30, 90]
  return windows.map((days) => participantUsers.filter((user) => {
    const joined = registrationDate(user)
    return joined ? daysBetween(joined, asOf) < days : false
  }).length)
}

export function buildOverviewAnalytics(bundle: OverviewAnalyticsBundle): AnalyticsYearData {
  const users = roleUsers(bundle.users)
  const asOf = latestObservedDate(users, bundle.groupActivity)
  const year = asOf.getUTCFullYear()
  const students = users.filter((user) => roleTitle(user.role) === 'Student')
  const mentors = users.filter((user) => roleTitle(user.role) === 'Mentor')
  const supervisors = users.filter((user) => roleTitle(user.role) === 'Supervisor')
  const groups = bundle.groups
  const groupsWithMentor = groups.filter((group) => groupMentors(group).length > 0).length
  const assignedMentorIds = new Set(
    groups.flatMap((group) => groupMentors(group).map((mentor) => String(mentor.id))),
  )
  const mentorUtilisation = percent(assignedMentorIds.size, mentors.length)
  const loggedInCount = users.filter((user) => user.hasLoggedIn).length
  const activeCount = users.filter((user) => user.isActive).length
  const deactivatedCount = users.filter((user) => !user.isActive || ['deactivated', 'suspended'].includes((user.accountStatus ?? '').toLowerCase())).length
  const registrationTrend = registrationsByRecentPeriods(users, asOf)
  const activity = buildActivityAnalytics(bundle)
  const messages = buildMessagesAnalytics(bundle)
  const resources = buildResourcesAnalytics(bundle)
  const email = buildEmailMonitoring(bundle)
  const unassignedStudents = students.filter((user) => !user.groupId).length
  const missingGuardian = students.filter((user) => !user.guardianEmail).length
  const pendingGuardian = students.filter((user) => !!user.guardianEmail && !user.joinPermissionReceived).length
  const inactiveMentors = mentors.filter((user) => !user.isActive).length
  const emailApproaching = email.mailboxes.some((mailbox) => mailbox.quotaLimit > 0 && mailbox.currentUsage / mailbox.quotaLimit >= 0.8)

  const result: AnalyticsYearData = {
    summary: [
      {
        label: 'Total Participants',
        value: String(users.length),
        helper: `${students.length} students · ${mentors.length} mentors · ${supervisors.length} supervisors`,
        trend: String(year),
        icon: 'users',
        tone: 'blue',
        source: 'live-api',
      },
      {
        label: 'Registered Groups',
        value: String(groups.length),
        helper: `${groupsWithMentor} with mentor · ${groups.length - groupsWithMentor} without mentor`,
        trend: String(year),
        icon: 'users',
        tone: 'purple',
        source: 'live-api',
      },
      {
        label: 'Mentor Utilisation',
        value: `${mentorUtilisation}%`,
        helper: `${assignedMentorIds.size} of ${mentors.length} mentors assigned to groups`,
        trend: String(year),
        icon: 'mentor',
        tone: 'teal',
        source: 'live-api',
      },
      {
        label: 'Logged In',
        value: `${percent(loggedInCount, users.length)}%`,
        helper: `${loggedInCount} of ${users.length} participants have logged in`,
        trend: String(year),
        icon: 'trend',
        tone: 'orange',
        source: 'live-api',
      },
    ],
    modules: [
      {
        key: 'registration', title: 'Registration', value: String(users.length), unit: 'Registrations',
        helper: 'Participant registrations from the live database', icon: 'user-plus', tone: 'blue', source: 'live-api',
        chart: registrationTrend,
      },
      {
        key: 'users', title: 'Users', value: String(users.length), unit: 'Total Users',
        helper: 'Current account status from the live database', icon: 'user', tone: 'purple', source: 'live-api',
        chart: [percent(activeCount, users.length), percent(deactivatedCount, users.length)],
        breakdown: [
          { label: 'Active', value: `${percent(activeCount, users.length)}%`, percent: percent(activeCount, users.length) },
          { label: 'Deactivated', value: `${percent(deactivatedCount, users.length)}%`, percent: percent(deactivatedCount, users.length) },
        ],
      },
      {
        key: 'groups', title: 'Groups', value: String(groups.length), unit: 'Groups',
        helper: 'Current group mentor coverage', icon: 'users', tone: 'teal', source: 'live-api',
        chart: [groupsWithMentor, groups.length - groupsWithMentor],
        breakdown: [
          { label: 'With mentor', value: String(groupsWithMentor), percent: percent(groupsWithMentor, groups.length) },
          { label: 'Without mentor', value: String(groups.length - groupsWithMentor), percent: percent(groups.length - groupsWithMentor, groups.length) },
        ],
      },
      {
        key: 'mentors', title: 'Mentors', value: `${mentorUtilisation}%`, unit: 'Utilised',
        helper: `${assignedMentorIds.size} mentors currently assigned to groups`, icon: 'mentor', tone: 'orange', source: 'live-api',
        chart: [mentorUtilisation],
      },
      {
        key: 'activity', title: 'Activity', value: activity.dailyActive === null ? '—' : String(activity.dailyActive), unit: 'Daily Active',
        helper: activity.loginHistoryAvailable ? 'Active users from recorded login events' : 'No recorded login history is available.', icon: 'activity', tone: 'blue', source: 'live-api',
        chart: activity.dailySeries.students.map((value, index) => value + activity.dailySeries.mentors[index] + activity.dailySeries.supervisors[index]),
      },
      {
        key: 'messages', title: 'Messages', value: messages.totalMessages.toLocaleString(), unit: 'Messages',
        helper: 'Messages stored in the live database', icon: 'message', tone: 'purple', source: 'live-api',
        chart: bundle.groupActivity.messages_by_day.slice(-7).map((row) => row.message_count),
      },
      {
        key: 'resources', title: 'Resources', value: resources.totalClicks.toLocaleString(), unit: 'Clicks',
        helper: 'Resource access events stored in the live database', icon: 'book', tone: 'teal', source: 'live-api',
        chart: resources.resources.slice(0, 3).map((row) => row.clicks),
        breakdown: resources.resources.slice(0, 3).map((row) => ({
          label: row.name, value: row.clicks.toLocaleString(), percent: resources.resources[0]?.clicks ? percent(row.clicks, resources.resources[0].clicks) : 0,
        })),
      },
      {
        key: 'email', title: 'Email Monitoring', value: email.overallStats.sent.toLocaleString(), unit: '24h recipients',
        helper: 'Announcement delivery attempts in the current rolling 24-hour window', icon: 'mail-check', tone: 'orange', source: 'live-api',
        chart: email.mailboxes.map((mailbox) => percent(mailbox.currentUsage, mailbox.quotaLimit)),
      },
    ],
    attention: [
      { label: 'Students not assigned to groups', value: unassignedStudents, icon: 'user', tone: 'red' as const, source: 'live-api' as const },
      { label: 'Groups without mentors', value: groups.length - groupsWithMentor, icon: 'users', tone: 'teal' as const, source: 'live-api' as const },
      { label: 'Inactive mentors', value: inactiveMentors, icon: 'mentor', tone: 'purple' as const, source: 'live-api' as const },
      { label: 'Deactivated accounts', value: deactivatedCount, icon: 'warning', tone: 'blue' as const, source: 'live-api' as const },
      { label: 'Missing guardian details', value: missingGuardian, icon: 'users', tone: 'red' as const, source: 'live-api' as const },
      { label: 'Guardian approvals pending', value: pendingGuardian, icon: 'mail-check', tone: 'orange' as const, source: 'live-api' as const },
      ...(emailApproaching
        ? [{ label: 'Email usage approaching limit', value: 1, icon: 'mail', tone: 'red' as const, source: 'live-api' as const }]
        : []),
    ].filter((item) => Number(item.value) > 0),
  }
  const missing = new Set(bundle.unavailableSources ?? [])
  const dependencies: Record<string, Array<(NonNullable<OverviewAnalyticsBundle['unavailableSources']>)[number]>> = {
    registration: ['users'], users: ['users'], groups: ['groups'], mentors: ['users', 'groups'],
    activity: ['users', 'loginActivity'], messages: ['users', 'groups', 'groupActivity'],
    resources: ['resourceAnalytics', 'resources'], email: ['emailAnalytics'],
  }
  for (const module of result.modules) {
    if (dependencies[module.key]?.some((source) => missing.has(source)) || (module.key === 'activity' && !activity.loginHistoryAvailable)) {
      module.unavailable = true
      module.value = '—'
      module.chart = []
      module.breakdown = undefined
      module.helper = module.key === 'activity' && !missing.has('users')
        ? 'No recorded login history is available.'
        : `${module.title} data is currently unavailable. Other modules remain available.`
    }
  }
  result.summary = result.summary.map((item) => {
    const unavailable = item.label === 'Registered Groups' ? missing.has('groups')
      : item.label === 'Mentor Utilisation' ? missing.has('users') || missing.has('groups') : missing.has('users')
    return unavailable ? { ...item, value: '—', helper: 'Data is currently unavailable.', unavailable: true } : item
  })
  result.attention = result.attention.filter((item) => {
    if (missing.has('users') && item.label !== 'Groups without mentors') return false
    if (missing.has('groups') && item.label === 'Groups without mentors') return false
    return !missing.has('emailAnalytics') || item.label !== 'Email usage approaching limit'
  })
  return result
}
