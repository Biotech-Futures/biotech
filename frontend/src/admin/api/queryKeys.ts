/**
 * Query-key conventions for the admin section.
 *
 * Every admin query/mutation keys off these factories so cache invalidation
 * stays consistent as screens are ported. Pattern per domain:
 *   all          -> root key, invalidate to refresh the whole domain
 *   list(params) -> a filtered/paginated list
 *   detail(id)   -> a single record
 *
 * Waves extend the factories as their screens land; don't hand-write key
 * arrays in components.
 */
type ListParams = Record<string, unknown>

function domain(name: string) {
  const all = ['admin', name] as const
  return {
    all,
    list: (params: ListParams = {}) => [...all, 'list', params] as const,
    detail: (id: number | string) => [...all, 'detail', id] as const,
  }
}

export const queryKeys = {
  summary: ['admin', 'summary'] as const,
  users: domain('users'),
  students: domain('students'),
  mentors: domain('mentors'),
  supervisors: domain('supervisors'),
  groups: domain('groups'),
  studentMatching: domain('student-matching'),
  mentorMatching: domain('mentor-matching'),
  matchedGroups: domain('matched-groups'),
  events: domain('events'),
  resources: domain('resources'),
  announcements: domain('announcements'),
  tasks: domain('tasks'),
}
