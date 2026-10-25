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
  type EmailSendToRecipient,
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

export type AnalyticsSource = keyof LiveBundle
export type AnalyticsAvailability = { unavailableSources?: AnalyticsSource[] }
export type ParticipantAnalyticsBundle = Pick<LiveBundle, 'users' | 'groupActivity' | 'loginActivity'> & AnalyticsAvailability
export type CoreAnalyticsBundle = ParticipantAnalyticsBundle & Pick<LiveBundle, 'groups'>
export type MentorAnalyticsBundle = CoreAnalyticsBundle & Pick<LiveBundle, 'mentors'>
export type ResourceAnalyticsBundle = Pick<LiveBundle, 'resourceAnalytics' | 'resources'> & AnalyticsAvailability
export type EmailAnalyticsBundle = ParticipantAnalyticsBundle & Pick<LiveBundle, 'emailAnalytics'>
export type OverviewAnalyticsBundle = CoreAnalyticsBundle & ResourceAnalyticsBundle & Pick<LiveBundle, 'emailAnalytics'>

export function analyticsSourceAvailable(bundle: AnalyticsAvailability, source: AnalyticsSource) {
  return !bundle.unavailableSources?.includes(source)
}

export const ANALYTICS_CACHE_TTL_MS = ANALYTICS_REFRESH_INTERVAL_MS

function createCachedLoader<T>(fetcher: (force: boolean) => Promise<T>) {
  let cached: Promise<T> | null = null
  let expiresAt = 0
  const load = (force = false) => {
    if (!cached || force || Date.now() >= expiresAt) {
      expiresAt = Number.POSITIVE_INFINITY
      const request = fetcher(force)
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

// One response cache shared by every Analytics page, keyed by source and date
// range. Moving between pages or back to a recent date range reuses the
// response instead of waiting for the same request again. Failed requests are
// never cached; entries expire with the page refresh interval.
const SOURCE_CACHE_LIMIT = 40
const sourceCache = new Map<string, { promise: Promise<unknown>; expiresAt: number }>()

function cachedRequest<T>(key: string, fetcher: () => Promise<T>, force = false): Promise<T> {
  const entry = sourceCache.get(key)
  if (entry && !force && Date.now() < entry.expiresAt) return entry.promise as Promise<T>
  const promise = fetcher()
  const record = { promise: promise as Promise<unknown>, expiresAt: Number.POSITIVE_INFINITY }
  sourceCache.delete(key)
  sourceCache.set(key, record)
  while (sourceCache.size > SOURCE_CACHE_LIMIT) {
    const oldest = sourceCache.keys().next().value
    if (oldest === undefined) break
    sourceCache.delete(oldest)
  }
  promise.then(
    () => { record.expiresAt = Date.now() + ANALYTICS_CACHE_TTL_MS },
    () => { if (sourceCache.get(key) === record) sourceCache.delete(key) },
  )
  return promise
}

const rangeKey = (start?: string, end?: string) => `${start ?? ''}..${end ?? ''}`

/** Group activity for a date range, served from the shared cache. */
export const loadGroupActivityRange = (start?: string, end?: string, force = false) =>
  cachedRequest(`groupActivity:${rangeKey(start, end)}`, () => fetchGroupActivity(start, end), force)

/** Login activity for a date range, served from the shared cache. */
export const loadLoginActivityRange = (start?: string, end?: string, force = false) =>
  cachedRequest(`loginActivity:${rangeKey(start, end)}`, () => fetchLoginActivity(start, end), force)

function inRange(date: string, start?: string, end?: string) {
  return (!start || date >= start) && (!end || date <= end)
}

/**
 * Derive a date-range group activity response from the full (unranged) one,
 * matching the API: every active group and member keeps its row (zero counts
 * included), and only message counts and daily rows depend on the range.
 * Returns null when the full response lacks the per-user daily breakdown.
 */
export function sliceGroupActivity(
  full: GroupActivityResponse,
  start?: string,
  end?: string,
): GroupActivityResponse | null {
  const userDaily = full.messages_by_user_by_group_by_day
  if (!userDaily) return null
  if (!start && !end) return full
  const groupDaily = full.messages_by_group_by_day.filter((row) => inRange(row.date, start, end))
  const userDailyInRange = userDaily.filter((row) => inRange(row.date, start, end))
  const groupTotals = new Map<number, number>()
  for (const row of groupDaily) groupTotals.set(row.group_id, (groupTotals.get(row.group_id) ?? 0) + row.message_count)
  const userTotals = new Map<number, number>()
  for (const row of userDailyInRange) userTotals.set(row.user_id, (userTotals.get(row.user_id) ?? 0) + row.message_count)
  return {
    ...full,
    messages_by_group: full.messages_by_group.map((row) => ({ ...row, message_count: groupTotals.get(row.group_id) ?? 0 })),
    messages_by_user: full.messages_by_user.map((row) => ({ ...row, message_count: userTotals.get(row.user_id) ?? 0 })),
    messages_by_day: full.messages_by_day.filter((row) => inRange(row.date, start, end)),
    messages_by_group_by_day: groupDaily,
    messages_by_user_by_group_by_day: userDailyInRange,
    mentor_activity_by_day: full.mentor_activity_by_day?.filter((row) => inRange(row.date, start, end)),
    query_range: { start: start ?? null, end: end ?? null },
  }
}

/**
 * Group activity for a range, computed on the client from the full response
 * whenever possible so changing dates is instant; otherwise fetched (cached).
 */
export function groupActivityForRange(full: GroupActivityResponse | undefined, start?: string, end?: string) {
  const sliced = full ? sliceGroupActivity(full, start, end) : null
  return sliced ? Promise.resolve(sliced) : loadGroupActivityRange(start, end)
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
    average_group_size_by_year: [],
    group_summary_by_year: [],
    query_range: { start: null, end: null },
  }
}

const sourceFetchers = {
  users: fetchAllUsers,
  groups: fetchAllGroups,
  mentors: fetchMentors,
  groupActivity: () => fetchGroupActivity(),
  loginActivity: () => fetchLoginActivity(),
  resourceAnalytics: () => fetchResourceAnalytics(),
  emailAnalytics: fetchEmailDeliveryAnalytics,
  resources: fetchAllResources,
}

const sourceLoaders = Object.fromEntries(
  (Object.keys(sourceFetchers) as AnalyticsSource[]).map((source) => [
    source,
    // Unranged sources share the same key as an unranged range request.
    (force = false) => cachedRequest(
      source === 'groupActivity' || source === 'loginActivity' ? `${source}:${rangeKey()}` : source,
      sourceFetchers[source] as () => Promise<unknown>,
      force,
    ),
  ]),
) as Record<AnalyticsSource, (force?: boolean) => Promise<unknown>>

function emptySources(): LiveBundle {
  return {
    users: [], groups: [], mentors: [], groupActivity: emptyGroupActivity(), loginActivity: undefined,
    resourceAnalytics: {
      total_clicks: 0, unique_users: 0, active_resources: 0,
      clicks_by_day: [], top_resources: [], clicks_by_resource_by_day: [], clicks_by_category: [],
      query_range: { start: null, end: null },
    },
    emailAnalytics: {
      snapshot_at: null, mailboxes: [], totals: { attempted: 0, delivered: 0, failed: 0, delivery_runs: 0 },
      hourly: [], daily: [], recent_deliveries: [], recent_sends: [],
    },
    resources: [],
  }
}

// Settle sources independently. Empty containers are only safe with their
// availability flags: views must never interpret a failed source as zero.
async function loadSources(sources: AnalyticsSource[], required: AnalyticsSource[] = [], force = false) {
  const results = await Promise.allSettled(sources.map((source) => sourceLoaders[source](force)))
  const unavailableSources = sources.filter((_, index) => results[index]?.status === 'rejected')
  if (unavailableSources.length === sources.length || required.some((source) => unavailableSources.includes(source))) {
    throw new Error('The data required for this view could not be loaded. Other analytics pages may still be available.')
  }
  const values = Object.fromEntries(results.flatMap((result, index) =>
    result.status === 'fulfilled' ? [[sources[index], result.value]] : [],
  ))
  return { ...emptySources(), ...values, unavailableSources } as LiveBundle & AnalyticsAvailability
}

// Cache per page so one page's failure or refresh does not invalidate another.
const usersPageLoader = createCachedLoader((force) => loadSources(['users', 'loginActivity'], ['users'], force))
const registrationPageLoader = createCachedLoader((force) => loadSources(['users'], ['users'], force))
const groupsPageLoader = createCachedLoader((force) => loadSources(['users', 'groups', 'groupActivity'], ['groups'], force))
const activityPageLoader = createCachedLoader((force) => loadSources(['users', 'groups', 'groupActivity', 'loginActivity'], [], force))
const messagesPageLoader = createCachedLoader((force) => loadSources(['users', 'groups', 'groupActivity'], ['groupActivity'], force))
const mentorsPageLoader = createCachedLoader((force) => loadSources(['users', 'groups', 'mentors', 'groupActivity'], ['mentors'], force))
const resourcesPageLoader = createCachedLoader((force) => loadSources(['resourceAnalytics', 'resources'], [], force))
const emailPageLoader = createCachedLoader((force) => loadSources(['emailAnalytics'], ['emailAnalytics'], force))
const overviewPageLoader = createCachedLoader((force) => loadSources([
  'users', 'groups', 'groupActivity', 'loginActivity', 'resourceAnalytics', 'emailAnalytics', 'resources',
], [], force))

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
  sourceCache.clear()
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

/**
 * Warm the shared cache with every Analytics source so opening any Analytics
 * page right after sign-in does not wait. Failures are ignored here; pages
 * report them when they load.
 */
export function prefetchAnalytics() {
  return Promise.allSettled(
    (Object.keys(sourceFetchers) as AnalyticsSource[]).map((source) => sourceLoaders[source]()),
  )
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
  // The admin users API exposes Django's User.date_joined as createdAt.
  // Invitation and activation timestamps describe later lifecycle events and
  // must not be used as substitutes for the account registration date.
  return safeDate(user.createdAt)
}

export type ParticipantYearCounts = {
  total: number
  students: number
  mentors: number
  supervisors: number
}

function participantCounts(users: AdminUser[]): ParticipantYearCounts {
  const rows = roleUsers(users)
  return {
    total: rows.length,
    students: rows.filter((user) => roleTitle(user.role) === 'Student').length,
    mentors: rows.filter((user) => roleTitle(user.role) === 'Mentor').length,
    supervisors: rows.filter((user) => roleTitle(user.role) === 'Supervisor').length,
  }
}

/** Registered by the end of `year`. Undated legacy accounts can only be
 *  represented safely in the live year. */
export function registeredByYear(user: AdminUser, year: number) {
  const joined = registrationDate(user)
  return joined ? joined.getUTCFullYear() <= year : year === new Date().getUTCFullYear()
}

export function participantYearComparison(users: AdminUser[], year: number) {
  const currentRows = roleUsers(users).filter((user) => registeredByYear(user, year))
  const previousRows = currentRows.filter((user) => {
    const joined = registrationDate(user)
    return joined !== null && joined.getUTCFullYear() <= year - 1
  })
  return {
    year,
    previousYear: year - 1,
    current: participantCounts(currentRows),
    previous: participantCounts(previousRows),
  }
}

export function groupYearComparison(groups: AdminGroup[], year: number) {
  const previous = groups.filter((group) => {
    const created = safeDate(group.createdAt)
    return created !== null && created.getUTCFullYear() <= year - 1
  }).length
  return { year, previousYear: year - 1, current: groups.length, previous }
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

export function usersAnalyticsAsOf(bundle: ParticipantAnalyticsBundle, year: number) {
  const activityDatesInYear = bundle.loginActivity?.by_day
    .map((row) => row.date)
    .filter((date) => Number(date.slice(0, 4)) === year)
    .sort()
  const latestActivityInYear = activityDatesInYear?.[activityDatesInYear.length - 1]

  if (latestActivityInYear) return latestActivityInYear
  if (year === new Date().getUTCFullYear()) return liveAnalyticsAsOf(bundle)
  return `${year}-12-31`
}

export function buildUsersAnalytics(
  bundle: ParticipantAnalyticsBundle,
  year = new Date().getUTCFullYear(),
): UserAnalyticsYear {
  const systemYear = new Date().getUTCFullYear()
  const users = roleUsers(bundle.users).filter((user) => registeredByYear(user, year))
  const asOf = safeDate(usersAnalyticsAsOf(bundle, year))
    ?? new Date(Date.UTC(year, 11, 31))
  // asOf is a whole UTC day, so only a login after that day happened after
  // the selected year. The live year's asOf is its latest day: keep every login.
  const cutoff = year === systemYear ? null : new Date(asOf.getTime() + 86_400_000)
  const loggedInAfterCutoff = (user: AdminUser) => {
    const last = safeDate(user.lastLogin)
    return cutoff !== null && last !== null && last >= cutoff
  }
  const students = users.filter((user) => roleTitle(user.role) === 'Student')
  const mentors = users.filter((user) => roleTitle(user.role) === 'Mentor')
  const supervisors = users.filter((user) => roleTitle(user.role) === 'Supervisor')

  // For the current year, last_login preserves whether each current user has
  // logged in this year, including logins before audit tracking was deployed.
  const loggedInThisYear = (rows: AdminUser[]) => rows.filter((user) =>
    safeDate(user.lastLogin)?.getUTCFullYear() === year,
  ).length
  const recordedYear = bundle.loginActivity?.by_year.find((row) => row.year === year)
  const loginCountByRole: Record<ActivityRole, number> = year === systemYear
    ? {
        Student: loggedInThisYear(students),
        Mentor: loggedInThisYear(mentors),
        Supervisor: loggedInThisYear(supervisors),
      }
    : {
        Student: recordedYear?.students ?? 0,
        Mentor: recordedYear?.mentors ?? 0,
        Supervisor: recordedYear?.supervisors ?? 0,
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
      if (!last || loggedInAfterCutoff(user)) return false
      const days = daysBetween(last, asOf)
      return days >= bucket.min && days <= bucket.max
    }).length,
  }))
  recency.push({
    label: 'Never',
    value: users.filter((user) => {
      const last = safeDate(user.lastLogin)
      return !last
    }).length,
  })

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
    // Login audit rows only exist for years with recorded logins.
    loginRatesAvailable: year === systemYear || recordedYear !== undefined,
    dailyActivity: { labels: dailyLabels, total: dailyTotal },
    lastLogin: recency,
    // A last login after a historical cutoff proves only that the account
    // logged in later; it cannot tell us whether the user had never logged in
    // by the selected year. Leave those rows out instead of mislabelling them
    // as "Never".
    userLastLogins: users.filter((user) => !loggedInAfterCutoff(user)).map((user) => {
      const recordedLastLogin = safeDate(user.lastLogin)
      const lastLoginDate = recordedLastLogin
      const activityStatus = lastLoginDate ? loginStatus(user, asOf) : 'Never'
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

// A group has at most 5 students. Group size counts students only; mentors and
// supervisors are not part of it.
export const MAX_STUDENTS_PER_GROUP = 5

function groupMentors(group: AdminGroup) {
  if (group.mentors) return group.mentors
  return group.mentor ? [group.mentor] : []
}

export function analyticsYears(bundle: Pick<LiveBundle, 'users' | 'groupActivity' | 'loginActivity'>) {
  const years = new Set<number>([new Date().getUTCFullYear()])
  for (const row of bundle.groupActivity.messages_by_day) years.add(Number(row.date.slice(0, 4)))
  for (const row of bundle.loginActivity?.by_day ?? []) years.add(Number(row.date.slice(0, 4)))
  for (const user of bundle.users) {
    const date = registrationDate(user)
    if (date) years.add(date.getUTCFullYear())
  }
  return [...years].filter(Number.isFinite).sort((a, b) => b - a)
}

export function groupAnalyticsYears(bundle: CoreAnalyticsBundle) {
  // Only offer years for which the backend supplied a complete year-end
  // snapshot. Group creation and message dates alone cannot reconstruct
  // historical membership distributions.
  const years = new Set<number>(
    (bundle.groupActivity.group_summary_by_year ?? [])
      .filter((row) => row.group_size_distribution !== undefined)
      .map((row) => row.year),
  )
  if (!years.size) years.add(new Date().getUTCFullYear())
  return [...years].filter(Number.isFinite).sort((a, b) => b - a)
}

export function buildGroupsAnalytics(
  bundle: CoreAnalyticsBundle,
  activityYear = liveAnalyticsYear(bundle),
): GroupsAnalyticsYear {
  const systemYear = new Date().getUTCFullYear()
  const groups = bundle.groups.filter((group) => {
    const created = safeDate(group.createdAt)
    return created ? created.getUTCFullYear() <= activityYear : activityYear === systemYear
  })
  const selectedSummary = bundle.groupActivity.group_summary_by_year
    ?.find((row) => row.year === activityYear)
  const selectedAverage = bundle.groupActivity.average_group_size_by_year
    ?.find((row) => row.year === activityYear)
  const historicalSummary = activityYear === systemYear ? undefined : selectedSummary
  const sizes = groups.map((group) => group.members.filter((member) => member.role.toLowerCase() === 'student').length)
  const localWithMentor = groups.filter((group) => groupMentors(group).length > 0).length
  const withMentor = selectedSummary?.groups_with_mentor ?? localWithMentor
  const totalGroups = selectedSummary?.group_count ?? groups.length
  const totalStudents = sizes.reduce((sum, value) => sum + value, 0)
  const averageGroupSize = selectedAverage?.average_group_size
    ?? (groups.length ? Number((totalStudents / groups.length).toFixed(1)) : 0)
  const previousAverageGroupSize = bundle.groupActivity.average_group_size_by_year
    ?.find((row) => row.year === activityYear - 1)?.average_group_size ?? null
  const previousGroupSummary = bundle.groupActivity.group_summary_by_year
    ?.find((row) => row.year === activityYear - 1)
  const groupSizeDistribution = historicalSummary?.group_size_distribution
    ?.map((bucket) => ({
      label: bucket.student_count > MAX_STUDENTS_PER_GROUP
        ? `Over ${MAX_STUDENTS_PER_GROUP}`
        : String(bucket.student_count),
      value: bucket.group_count,
    }))
    ?? Array.from({ length: MAX_STUDENTS_PER_GROUP + 1 }, (_, size) => ({
      label: String(size),
      value: sizes.filter((value) => value === size).length,
    }))
  // Groups above the limit are shown only when they exist, so data problems
  // stay visible without a permanently empty bucket.
  const overCapacity = historicalSummary?.over_capacity_groups
    ?? sizes.filter((size) => size > MAX_STUDENTS_PER_GROUP).length
  if (!historicalSummary && overCapacity) {
    groupSizeDistribution.push({ label: `Over ${MAX_STUDENTS_PER_GROUP}`, value: overCapacity })
  }

  const activityDates = bundle.groupActivity.messages_by_day
    .map((row) => row.date)
    .filter((date) => Number(date.slice(0, 4)) === activityYear)
    .sort()
  const recentEnd = activityDates[activityDates.length - 1]
    ?? (activityYear === systemYear ? liveAnalyticsAsOf(bundle) : `${activityYear}-12-31`)
  const recentStartDate = new Date(`${recentEnd}T00:00:00Z`)
  recentStartDate.setUTCDate(recentStartDate.getUTCDate() - 6)
  const recentStart = recentStartDate.toISOString().slice(0, 10)
  const recentGroupIds = new Set(
    bundle.groupActivity.messages_by_group_by_day
      .filter((row) => row.date >= recentStart && row.date <= recentEnd && row.message_count > 0)
      .map((row) => String(row.group_id)),
  )
  const messagesThroughSelectedYear = new Set(
    bundle.groupActivity.messages_by_group_by_day
      .filter((row) => Number(row.date.slice(0, 4)) <= activityYear && row.message_count > 0)
      .map((row) => String(row.group_id)),
  )
  const active = historicalSummary?.active_groups
    ?? groups.filter((group) => recentGroupIds.has(String(group.id))).length
  const notStarted = historicalSummary?.not_started_groups
    ?? groups.filter(
      (group) => !messagesThroughSelectedYear.has(String(group.id)) && group.members.length === 0,
    ).length
  const inactive = historicalSummary?.inactive_groups
    ?? Math.max(0, totalGroups - active - notStarted)

  return {
    totalGroups,
    groupGrowth: null,
    averageGroupSize,
    averageGroupSizePrevious: previousAverageGroupSize,
    averageGroupSizePreviousYear: activityYear - 1,
    avgSizeChange: previousAverageGroupSize && previousAverageGroupSize > 0
      ? Number((((averageGroupSize - previousAverageGroupSize) / previousAverageGroupSize) * 100).toFixed(1))
      : null,
    groupsWithMentor: withMentor,
    groupsWithoutMentor: selectedSummary?.groups_without_mentor ?? Math.max(groups.length - withMentor, 0),
    mentorStudentRatio: selectedSummary?.students_per_mentor ?? (() => {
      const mentoredGroups = groups.filter((group) => groupMentors(group).length > 0)
      const mentorAssignments = mentoredGroups.reduce((sum, group) => sum + groupMentors(group).length, 0)
      const assignedStudents = mentoredGroups.reduce(
        (sum, group) => sum + group.members.filter((member) => member.role.toLowerCase() === 'student').length,
        0,
      )
      return mentorAssignments ? Number((assignedStudents / mentorAssignments).toFixed(2)) : null
    })(),
    comparisonPreviousYear: activityYear - 1,
    groupsWithMentorPrevious: previousGroupSummary?.groups_with_mentor ?? null,
    groupsWithoutMentorPrevious: previousGroupSummary?.groups_without_mentor ?? null,
    mentorStudentRatioPrevious: previousGroupSummary?.students_per_mentor ?? null,
    smallGroups: historicalSummary?.small_groups ?? sizes.filter((size) => size < 3).length,
    inactiveRecent: inactive + notStarted,
    nearCapacity: historicalSummary?.full_groups
      ?? sizes.filter((size) => size === MAX_STUDENTS_PER_GROUP).length,
    overCapacity,
    groupSizeDistribution,
    groupStatus: [
      { label: 'Active', value: active, color: BTF_COLORS.darkGreen },
      { label: 'Inactive', value: inactive, color: BTF_COLORS.mintGreen },
      { label: 'Not started', value: notStarted, color: BTF_COLORS.lightGreen },
    ],
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
      type: meta?.resource_type ?? (analyticsSourceAvailable(bundle, 'resources') ? 'Uncategorised' : 'Unavailable'),
      roles,
    }
  })
  return {
    totalClicks: analytics.total_clicks,
    uniqueUsers: analytics.unique_users,
    activeResources: analytics.active_resources,
    mostUsedResource: analytics.top_resources[0]?.resource_name ?? '—',
    dailyClicks: analytics.clicks_by_day.map((row) => ({ label: row.date, clicks: row.click_count })),
    // null when the backend does not provide per-resource daily usage yet.
    resourceDaily: analytics.clicks_by_resource_by_day?.map((row) => ({
      date: row.date,
      resourceId: row.resource_id,
      name: row.resource_name,
      clicks: row.click_count,
      uniqueUsers: row.unique_users,
    })) ?? null,
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
      region: mentor.countryName,
      interests: mentor.interests,
      institution: mentor.institution,
      accountActive: mentor.accountStatus ? mentor.accountStatus === 'active' : mentor.isActive,
      accountStatus: mentor.accountStatus ?? null,
      email: mentor.email,
      lastLogin: mentor.lastLogin,
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
      hour,
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
      date,
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
    logs: email.recent_sends
      ? email.recent_sends.map((row) => ({
          // A send still going has no id yet; its delivery row's id, negated,
          // keeps the row apart from finished sends.
          id: row.id ?? -(row.delivery_id ?? 0),
          sender: row.initiated_by_name || 'System',
          senderEmail: row.initiated_by_email || '—',
          recipient: recipientCount(row.attempted),
          recipientEmail: '—',
          title: row.title ?? row.email_type_label,
          type: row.email_type_label,
          sentAt: formatLogTime(row.started_at),
          sentAtIso: row.started_at,
          status: logStatus(row.status, row.delivered, row.failed, row.status === 'sending'),
          attempted: row.attempted,
          delivered: row.delivered,
          failed: row.failed,
          sendId: row.id,
          recipientsRecorded: row.recipients_recorded ?? 0,
        }))
      : email.recent_deliveries.map((row) => ({
          id: row.id,
          sender: row.initiated_by_name || 'System',
          senderEmail: row.initiated_by_email || '—',
          recipient: `Announcement audience (${row.recipient_count})`,
          recipientEmail: '—',
          title: row.title,
          type: 'Announcement notification',
          sentAt: formatLogTime(row.started_at),
          sentAtIso: row.started_at,
          status: logStatus(
            row.status,
            row.success_count,
            row.failure_count,
            isRecentIncompleteAnnouncement(row, email.snapshot_at),
          ),
          attempted: row.recipient_count,
          delivered: row.success_count,
          failed: row.failure_count,
          sendId: null,
          recipientsRecorded: 0,
        })),
  }
}

/** One row per email sent to a matching recipient, for the recipient search. */
export function buildRecipientEmailLogs(rows: EmailSendToRecipient[]): EmailLog[] {
  return rows.map((row) => ({
    id: row.id,
    sender: row.initiated_by_name || 'System',
    senderEmail: row.initiated_by_email || '—',
    recipient: row.recipient.name || '—',
    recipientEmail: row.recipient.email,
    title: row.title ?? row.email_type_label,
    type: row.email_type_label,
    sentAt: formatLogTime(row.started_at),
    sentAtIso: row.started_at,
    status: row.recipient.status === 'delivered' ? 'Delivered' : 'Failed',
    attempted: row.attempted,
    delivered: row.delivered,
    failed: row.failed,
    sendId: row.id,
    recipientsRecorded: row.attempted,
    recipientReason: row.recipient.status === 'delivered' ? '' : (row.recipient.reason || "couldn't be sent"),
  }))
}

function logStatus(status: string, delivered: number, failed: number, sending = false): EmailLog['status'] {
  if (sending) return 'Sending'
  // Counts describe the completed result more reliably than a stale status
  // value left behind by an interrupted or older delivery workflow.
  if (delivered > 0 && failed > 0) return 'Partial'
  if (delivered > 0) return 'Delivered'
  if (failed > 0) return 'Failed'
  if (status === 'partial') return 'Partial'
  if (status === 'failed') return 'Failed'
  return 'Delivered'
}

const EMAIL_SENDING_GRACE_MS = 30 * 60 * 1000

function isRecentIncompleteAnnouncement(
  row: EmailDeliveryAnalyticsResponse['recent_deliveries'][number],
  snapshotAt: string | null,
) {
  const incomplete = row.completed_at === null
    || (row.completed_at === undefined
      && row.recipient_count > 0
      && row.success_count + row.failure_count === 0)
  if (!incomplete) return false

  const started = safeDate(row.started_at)
  const snapshot = safeDate(snapshotAt) ?? new Date()
  if (!started) return false
  const elapsed = snapshot.getTime() - started.getTime()
  return elapsed >= 0 && elapsed <= EMAIL_SENDING_GRACE_MS
}

const recipientCount = (count: number) => `${count} recipient${count === 1 ? '' : 's'}`

const formatLogTime = (value: string) => new Date(value).toLocaleString('en-AU', {
  dateStyle: 'medium',
  timeStyle: 'short',
})

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
          { label: 'Inactive', value: `${percent(deactivatedCount, users.length)}%`, percent: percent(deactivatedCount, users.length) },
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
        helper: 'Email delivery attempts (every email type) in the current rolling 24-hour window', icon: 'mail-check', tone: 'orange', source: 'live-api',
        chart: email.mailboxes.map((mailbox) => percent(mailbox.currentUsage, mailbox.quotaLimit)),
      },
    ],
    attention: [
      { label: 'Students not assigned to groups', value: unassignedStudents, icon: 'user', tone: 'red' as const, source: 'live-api' as const },
      { label: 'Groups without mentors', value: groups.length - groupsWithMentor, icon: 'users', tone: 'teal' as const, source: 'live-api' as const },
      { label: 'Inactive mentors', value: inactiveMentors, icon: 'mentor', tone: 'purple' as const, source: 'live-api' as const },
      { label: 'Inactive accounts', value: deactivatedCount, icon: 'warning', tone: 'blue' as const, source: 'live-api' as const },
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
    activity: ['loginActivity'], messages: ['groupActivity'],
    resources: ['resourceAnalytics'], email: ['emailAnalytics'],
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
    if (missing.has('users') && !['Groups without mentors', 'Email usage approaching limit'].includes(item.label)) return false
    if (missing.has('groups') && item.label === 'Groups without mentors') return false
    return !missing.has('emailAnalytics') || item.label !== 'Email usage approaching limit'
  })
  return result
}
