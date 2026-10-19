import type { CoreAnalyticsBundle } from '@/utils/liveAnalyticsData'
import { liveAnalyticsAsOf } from '@/utils/liveAnalyticsData'

export type GroupActivityDetailStatus = 'Active' | 'Inactive' | 'Not started'

export type GroupActivityDetailRow = {
  id: string
  name: string
  mentors: string[]
  status: GroupActivityDetailStatus
  lastActiveDate: string | null
  daysSinceActive: number | null
}

function isoDay(value: string) {
  const day = value.slice(0, 10)
  const parsed = new Date(`${day}T00:00:00Z`)
  return Number.isNaN(parsed.getTime()) ? null : day
}

function daysBetween(start: string, end: string) {
  const startTime = new Date(`${start}T00:00:00Z`).getTime()
  const endTime = new Date(`${end}T00:00:00Z`).getTime()
  return Math.max(0, Math.floor((endTime - startTime) / 86_400_000))
}

function mentorNames(group: CoreAnalyticsBundle['groups'][number]) {
  const mentors = group.mentors === undefined
    ? (group.mentor ? [group.mentor] : [])
    : group.mentors

  return [...new Map(mentors.map((mentor) => [mentor.id, mentor.name])).values()]
}

/**
 * Builds the Activity page's current group directory exclusively from live API rows.
 * Message activity is day-granular, so this deliberately exposes no fabricated time of day.
 * The status is an explicitly provisional demo heuristic, not an approved product definition.
 */
export function buildGroupActivityDetailRows(
  bundle: CoreAnalyticsBundle,
): GroupActivityDetailRow[] {
  const asOf = liveAnalyticsAsOf(bundle)
  const recentStartDate = new Date(`${asOf}T00:00:00Z`)
  recentStartDate.setUTCDate(recentStartDate.getUTCDate() - 6)
  const recentStart = recentStartDate.toISOString().slice(0, 10)

  const messageTotals = new Map(
    bundle.groupActivity.messages_by_group.map((row) => [String(row.group_id), row.message_count]),
  )
  const lastMessageByGroup = new Map<string, string>()
  const recentlyActiveGroupIds = new Set<string>()

  for (const row of bundle.groupActivity.messages_by_group_by_day) {
    if (row.message_count <= 0) continue
    const date = isoDay(row.date)
    if (!date) continue
    const groupId = String(row.group_id)
    const previous = lastMessageByGroup.get(groupId)
    if (!previous || date > previous) lastMessageByGroup.set(groupId, date)
    if (date >= recentStart && date <= asOf) recentlyActiveGroupIds.add(groupId)
  }

  return bundle.groups.map((group) => {
    const lastActiveDate = lastMessageByGroup.get(group.id) ?? null
    const status: GroupActivityDetailStatus = recentlyActiveGroupIds.has(group.id)
      ? 'Active'
      : (messageTotals.get(group.id) ?? 0) === 0 && group.members.length === 0
        ? 'Not started'
        : 'Inactive'

    return {
      id: group.id,
      name: group.name,
      mentors: mentorNames(group),
      status,
      lastActiveDate,
      daysSinceActive: lastActiveDate ? daysBetween(lastActiveDate, asOf) : null,
    }
  })
}
