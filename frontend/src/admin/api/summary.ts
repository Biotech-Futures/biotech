/**
 * Admin operational summary — GET /api/v1/admin/summary/.
 *
 * First domain file; the wave ports follow this shape: types + query
 * composables per domain, all through the shared client and queryKeys.
 */
import { useQuery } from '@tanstack/vue-query'
import { adminApi } from '@/admin/api/client'
import { queryKeys } from '@/admin/api/queryKeys'

export interface AdminSummary {
  active_users: number
  invited_or_pending_users: number
  suspended_or_deactivated_users: number
  active_groups: number
  groups_without_mentor: number
  unassigned_match_recommendations: number
  upcoming_events: number
}

export function useAdminSummaryQuery() {
  return useQuery({
    queryKey: queryKeys.summary,
    queryFn: () => adminApi.get<AdminSummary>('/summary'),
    // Counts go stale fast while admins work in other tabs; refresh on return.
    refetchOnMount: true,
  })
}
