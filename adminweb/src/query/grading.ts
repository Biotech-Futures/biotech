import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/myFetch";
import type {
  ComponentListPayload,
  Grade,
  GradeBulkItem,
  GroupMarkingPayload,
} from "@/type/grading";

const QUERY_KEY = "grading";

// GET /api/v1/grading/groups/{id}/ — composite marking payload for one group.
// apiFetch (not myFetch) because grading lives at /api/v1/grading/, not
// /api/v1/admin/grading/.
export function useQueryGroupMarking(groupId: number, year?: number) {
  return useQuery({
    queryKey: [QUERY_KEY, "group", groupId, year ?? null],
    queryFn: async () => {
      const res = await apiFetch.get<GroupMarkingPayload>(
        `/grading/groups/${groupId}/`,
        { params: year ? { year } : undefined },
      );
      return res.data;
    },
    enabled: Number.isFinite(groupId) && groupId > 0,
  });
}

// GET /api/v1/grading/components/{code}/ — table payload for the per-component
// marking flow ("sit down and mark all posters"). The same query key powers
// both the table view and the detail view's prev/next navigation, so a click
// through the table lands on a warm cache.
export function useQueryComponentRows(code: string, year?: number) {
  return useQuery({
    queryKey: [QUERY_KEY, "component", code, year ?? null],
    queryFn: async () => {
      const res = await apiFetch.get<ComponentListPayload>(
        `/grading/components/${code}/`,
        { params: year ? { year } : undefined },
      );
      return res.data;
    },
    enabled: Boolean(code),
  });
}

// POST /api/v1/grading/grades/bulk/ — upsert many grades in one round trip.
export function useSaveGradesBulk() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ groupId, items }: { groupId: number; items: GradeBulkItem[] }) => {
      const res = await apiFetch.post<Grade[]>(`/grading/grades/bulk/`, { items });
      return { groupId, grades: res.data };
    },
    onSuccess: ({ groupId }) => {
      void qc.invalidateQueries({ queryKey: [QUERY_KEY, "group", groupId] });
      // Progress column in the per-component table depends on grade counts;
      // invalidate the whole "component" slice so any open component view
      // (and stale caches for other components) refetches on next view.
      void qc.invalidateQueries({ queryKey: [QUERY_KEY, "component"] });
    },
  });
}

// PATCH /api/v1/grading/grades/{id}/ — inline edit for a single grade.
export function useUpdateGrade() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      gradeId,
      mark,
      comment,
    }: {
      gradeId: number;
      mark?: string | null;
      comment?: string;
    }) => {
      const res = await apiFetch.patch<Grade>(`/grading/grades/${gradeId}/`, {
        mark,
        comment,
      });
      return res.data;
    },
    onSuccess: () => {
      // Broad invalidation — the marking page reloads its whole payload; cheap
      // and avoids surgical cache patching until multiple views share this data.
      void qc.invalidateQueries({ queryKey: [QUERY_KEY] });
    },
  });
}
