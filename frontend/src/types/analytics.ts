export type ActivityRole = 'Student' | 'Mentor' | 'Supervisor'
export type ActivityStatus = 'Active' | 'Inactive' | 'Never'

export type ActivityUser = {
  id: number
  name: string
  role: ActivityRole
  lastLogin: string | null
  daysInactive: number | null
  daysActive: number | null
  status: ActivityStatus
  isActive?: boolean
  accountStatus?: string | null
}

export type ActivityAnalyticsData = {
  totalUsers: number
  dailyActive: number | null
  weeklyActive: number | null
  monthlyActive: number | null
  loginHistoryAvailable?: boolean
  loggedInRate: number
  neverLoggedIn: number
  dailySeries: {
    students: number[]
    mentors: number[]
    supervisors: number[]
  }
  roleLoginRates: Array<{ role: ActivityRole; value: number }>
  loginRecency: Array<{ label: string; value: number }>
  users: ActivityUser[]
}

export type AnalyticsMetricSource = 'live-api' | 'seed-derived' | 'mock-only'

export interface AnalyticsMetric {
  unavailable?: boolean
  label: string
  value: string
  helper: string
  trend?: string
  icon: string
  tone: 'blue' | 'purple' | 'teal' | 'orange'
  source: AnalyticsMetricSource
}

export interface AnalyticsModule {
  unavailable?: boolean
  key: string
  title: string
  value: string
  unit: string
  helper: string
  icon: string
  tone: 'blue' | 'purple' | 'teal' | 'orange'
  source: AnalyticsMetricSource
  chart: number[]
  breakdown?: Array<{ label: string; value: string; percent?: number }>
}

export interface AnalyticsAttentionItem {
  label: string
  value: number
  icon: string
  tone: 'red' | 'orange' | 'purple' | 'blue' | 'teal'
  source: AnalyticsMetricSource
}

export interface AnalyticsYearData {
  summary: AnalyticsMetric[]
  modules: AnalyticsModule[]
  attention: AnalyticsAttentionItem[]
}

export type GroupsAnalyticsYear = {
  totalGroups: number
  groupGrowth: number | null
  averageGroupSize: number
  averageGroupSizePrevious: number | null
  averageGroupSizePreviousYear: number
  avgSizeChange: number | null
  groupsWithMentor: number
  groupsWithoutMentor: number
  mentorStudentRatio: number | null
  comparisonPreviousYear: number
  groupsWithMentorPrevious: number | null
  groupsWithoutMentorPrevious: number | null
  mentorStudentRatioPrevious: number | null
  smallGroups: number
  inactiveRecent: number
  nearCapacity: number
  overCapacity: number
  groupSizeDistribution: Array<{ label: string; value: number }>
  groupStatus: Array<{ label: string; value: number; color: string }>
  groupActivity: Array<{ month: string; active: number; inactive: number }>
}

export type CountItem = { id?: number; name: string; value: number }
export type UserCountItem = CountItem & { role: string }

export type MessagesAnalyticsYear = {
  totalMessages: number
  totalGroups: number
  groupsWithMessages: number
  groups: CountItem[]
  users: UserCountItem[]
  monthly: number[]
  weekly: number[]
  monthWeeks: number[]
}

export type RegistrationSource = 'Individual' | 'Supervisor' | 'Team / peer' | 'Spreadsheet'
export type RegistrationIssue = 'missing_guardian' | 'awaiting_approval'
export type RegistrationTrendPoint = { date: string; students: number; mentors: number }
export type RegistrationFollowUp = {
  id: number
  student: string
  email: string
  supervisor: string
  registrationDate: string
  daysOutstanding: number
  source: RegistrationSource | null
  issue: RegistrationIssue
}

export type ResourceUsageItem = {
  id: number
  name: string
  clicks: number
  uniqueUsers: number
  type: string
  roles: Array<'Student' | 'Mentor' | 'Supervisor'>
}

export type UserAnalyticsYear = {
  totalUsers: number
  students: number
  mentors: number
  supervisors: number
  totalGrowth: number | null
  studentGrowth: number | null
  mentorGrowth: number | null
  supervisorGrowth: number | null
  loginRates: { students: number; mentors: number; supervisors: number }
  // False for a past year with no recorded logins, so its rates are unknown rather than 0%.
  loginRatesAvailable: boolean
  dailyActivity: { labels: string[]; total: number[] }
  lastLogin: Array<{ label: string; value: number }>
  userLastLogins: Array<{
    id?: number | string
    name: string
    role: ActivityRole
    lastLogin: string
    lastLoginIso?: string | null
    daysInactive?: number | null
    status: 'Recent' | 'Inactive' | 'Never'
  }>
  registration: { students: number[]; mentors: number[]; supervisors: number[] }
  regions: Array<{ name: string; value: number }>
  interests: Array<{ name: string; students: number; mentors: number }>
}

export type MentorStatus = 'active' | 'inactive' | 'onboarding'
export type MentorBackground = 'industry' | 'undergraduate' | 'postgraduate' | 'hdr' | 'unknown'
export interface AnalyticsMentor {
  id: string
  name: string
  status: MentorStatus
  background: MentorBackground
  capacity: number
  groupIds: string[]
  studentIds: string[]
  region: string | null
  interests: string[]
  institution: string | null
  // Whether the mentor's account is activated (account_status "active").
  accountActive?: boolean
  // Account status as sent by the mentor source, e.g. "active" or "deactivated".
  accountStatus?: string | null
  email?: string
  // Last successful login on the account (ISO timestamp), when the mentor
  // source provides it; undefined falls back to login events.
  lastLogin?: string | null
}
export type DemoMentor = AnalyticsMentor

/** One resource's usage on one UTC day. */
export interface ResourceDailyUsage {
  date: string
  resourceId: number
  name: string
  clicks: number
  uniqueUsers: number
}
export interface MentorEvent {
  mentorId: string
  date: string
  logins: number
  messages: number
}

export type EmailLog = {
  id: number
  sender: string
  senderEmail: string
  recipient: string
  recipientEmail: string
  title: string
  type: string
  sentAt: string
  // ISO 8601 UTC time of the send, for exports.
  sentAtIso: string
  status: 'Sending' | 'Delivered' | 'Partial' | 'Opened' | 'Failed'
  attempted: number
  delivered: number
  failed: number
  // The send behind the row (null for legacy announcement rows) and how many
  // of its recipients were recorded, for exporting the recipient list.
  sendId: number | null
  recipientsRecorded: number
  // Set when the row is one recipient's copy (recipient search): why it did
  // not reach them, or "" when it did.
  recipientReason?: string
}

export type EmailMonitoringData = {
  mailboxes: Array<{ email: string; currentUsage: number; quotaLimit: number }>
  sentLastHour: number
  peakHourLabel: string
  peakHourValue: number
  hourlyUsage: Array<{ hour: string; label: string; info: number; connect: number }>
  verificationDaily: Array<{ date: string; label: string; value: number }>
  verificationDailyBaseLimit: number
  statusByRole: Array<{
    role: 'Students' | 'Mentors' | 'Supervisors'
    attempted: number
    delivered: number
    opened: number | null
    failed: number
    trackedDeliveries: number
  }>
  roleAttribution: {
    basis: 'current_single_role_audience'
    available: boolean
    complete: boolean
    trackedDeliveryRuns: number
    unattributedDeliveryRuns: number
    trackedAttempted: number
    unattributedAttempted: number
    trackedDelivered: number
    unattributedDelivered: number
    trackedFailed: number
    unattributedFailed: number
  }
  categories: Array<{ label: string; value: number; color: string }>
  alerts: Array<{
    id: number
    time: string
    type: string
    detail: string
    status: 'Resolved' | 'Monitoring'
  }>
  overallStats: {
    delivered: number
    sent: number
    failed: number
    clicked: number | null
    opened: number | null
    spam: number | null
    averageSentPerUser: number | null
    averageOpenedPerUser: number | null
    averageClickedPerUser: number | null
  }
  logs: EmailLog[]
}
