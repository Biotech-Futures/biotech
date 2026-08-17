import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/myFetch";
import type {
  BulkUploadResponse,
  ComponentListPayload,
  FinalistListResponse,
  Grade,
  GradeBulkItem,
  GradingJobDetail,
  GradingSettingsDetail,
  GroupMarkingPayload,
  MarksReleaseDetail,
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

// GET /api/v1/grading/groups/{id}/download/ — sync zip fetch, then trigger a
// browser download from the resulting blob. Axios (via apiFetch) sends the
// session cookie; a plain <a href> wouldn't when the API is on a different
// origin than the SPA dev server.
export function useDownloadGroupZip() {
  return useMutation({
    mutationFn: async ({ groupId, component }: { groupId: number; component?: string }) => {
      const res = await apiFetch.get(`/grading/groups/${groupId}/download/`, {
        params: component ? { component } : undefined,
        responseType: "blob",
      });
      const disp = (res.headers["content-disposition"] ?? "") as string;
      const match = /filename="?([^";]+)"?/.exec(disp);
      const filename = match?.[1] ?? `group-${groupId}.zip`;
      triggerBlobDownload(new Blob([res.data], { type: "application/zip" }), filename);
    },
  });
}

// POST /api/v1/grading/components/{code}/download/ — kicks off a GradingJob,
// returns { job_id }. Caller polls useJobStatus(job_id) to know when to fetch.
export function useStartComponentDownload() {
  return useMutation({
    mutationFn: async ({
      code,
      format,
      groupIds,
    }: {
      code: string;
      format: "zip" | "xlsx";
      groupIds?: number[];
    }) => {
      const res = await apiFetch.post<{ job_id: number }>(
        `/grading/components/${code}/download/`,
        { format, group_ids: groupIds ?? null },
      );
      return res.data.job_id;
    },
  });
}

// GET /api/v1/grading/jobs/{id}/ — polls every 2s while pending/running.
export function useJobStatus(jobId: number | null) {
  return useQuery({
    queryKey: [QUERY_KEY, "job", jobId],
    queryFn: async () => {
      const res = await apiFetch.get<GradingJobDetail>(`/grading/jobs/${jobId}/`);
      return res.data;
    },
    enabled: jobId != null,
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s === "done" || s === "failed" ? false : 2000;
    },
  });
}

// POST /api/v1/grading/components/<code>/bulk-upload/ — multipart with a
// spreadsheet file. Same mutation for preview and apply; caller flips
// `dryRun` to switch modes. Backend re-parses on apply so the diff we
// commit reflects current DB state (not just what was previewed).
export function useBulkUploadMarks() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      code,
      file,
      dryRun,
    }: {
      code: string;
      file: File;
      dryRun: boolean;
    }): Promise<BulkUploadResponse> => {
      const form = new FormData();
      form.append("file", file);
      form.append("dry_run", dryRun ? "true" : "false");
      const res = await apiFetch.post<BulkUploadResponse>(
        `/grading/components/${code}/bulk-upload/`,
        form,
        { headers: { "Content-Type": "multipart/form-data" } },
      );
      return res.data;
    },
    onSuccess: (data, vars) => {
      if (data.applied) {
        void qc.invalidateQueries({ queryKey: [QUERY_KEY, "component", vars.code] });
        void qc.invalidateQueries({ queryKey: [QUERY_KEY, "group"] });
      }
    },
  });
}

// GET /api/v1/grading/release/ — current release status.
export function useMarksRelease() {
  return useQuery({
    queryKey: [QUERY_KEY, "release"],
    queryFn: async () => {
      const res = await apiFetch.get<MarksReleaseDetail>("/grading/release/");
      return res.data;
    },
  });
}

// POST /api/v1/grading/release/ — flip release on (or off with release=false).
export function useToggleRelease() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ release }: { release: boolean }) => {
      const res = await apiFetch.post<MarksReleaseDetail>("/grading/release/", { release });
      return res.data;
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [QUERY_KEY, "release"] });
    },
  });
}

// GET/PATCH /api/v1/grading/settings/ — director names + template uploads.
export function useGradingSettings() {
  return useQuery({
    queryKey: [QUERY_KEY, "settings"],
    queryFn: async () => {
      const res = await apiFetch.get<GradingSettingsDetail>("/grading/settings/");
      return res.data;
    },
  });
}

export function useUpdateGradingSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (patch: Partial<GradingSettingsDetail> | FormData) => {
      const isFormData = patch instanceof FormData;
      const res = await apiFetch.patch<GradingSettingsDetail>("/grading/settings/", patch, {
        headers: isFormData ? { "Content-Type": "multipart/form-data" } : undefined,
      });
      return res.data;
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [QUERY_KEY, "settings"] });
    },
  });
}

// Finalist flag CRUD. Toggle is per-group; list is the current set.
export function useFinalists() {
  return useQuery({
    queryKey: [QUERY_KEY, "finalists"],
    queryFn: async () => {
      const res = await apiFetch.get<FinalistListResponse>("/grading/finalists/");
      return res.data;
    },
  });
}

export function useToggleFinalist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      groupId,
      flagged,
      notify,
    }: {
      groupId: number;
      flagged: boolean;
      notify?: boolean;
    }) => {
      if (flagged) {
        await apiFetch.post(`/grading/groups/${groupId}/finalist/`, { notify: !!notify });
      } else {
        await apiFetch.delete(`/grading/groups/${groupId}/finalist/`);
      }
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [QUERY_KEY, "finalists"] });
    },
  });
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
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
