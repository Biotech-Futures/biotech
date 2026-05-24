import { myFetch } from "@/lib/myFetch";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  AdminScope,
  ApiResponse,
  StateOption,
  Track,
} from "@/type/track";

const BASE = "/track";

export function useListTracks(includeArchived: boolean = false) {
  return useQuery({
    queryKey: ["tracks", includeArchived],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (includeArchived) params.set("includeArchived", "true");
      const url = params.toString() ? `${BASE}?${params}` : BASE;
      const res = await myFetch.get<ApiResponse<Track[]>>(url);
      return res.data.data;
    },
  });
}

export function useListStates() {
  return useQuery({
    queryKey: ["track-states"],
    queryFn: async () => {
      const res = await myFetch.get<ApiResponse<StateOption[]>>(
        `${BASE}/states`,
      );
      return res.data.data;
    },
  });
}

export function useCreateTrack() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (data: { track_name: string; state_id: number }) => {
      const res = await myFetch.post<ApiResponse<Track | null>>(BASE, data);
      return res.data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tracks"] }),
  });
}

const TRACK_STATE_DEPENDENT_KEYS = [
  ["tracks"],
  ["event-meta-tracks"],
  ["event-meta-groups"],
  ["users"],
  ["students"],
  ["groups"],
  ["events"],
  ["announcements"],
  ["mentorList"],
  ["matchedGroups"],
  ["unmatchedGroups"],
  ["matchInfo"],
] as const;

function invalidateTrackDependents(qc: ReturnType<typeof useQueryClient>) {
  for (const key of TRACK_STATE_DEPENDENT_KEYS) {
    qc.invalidateQueries({ queryKey: key });
  }
}

export function useArchiveTrack() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (trackId: number) => {
      const res = await myFetch.post<ApiResponse<Track | null>>(
        `${BASE}/${trackId}/archive`,
        {},
      );
      return res.data;
    },
    onSuccess: () => invalidateTrackDependents(qc),
  });
}

export function useRestoreTrack() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (trackId: number) => {
      const res = await myFetch.post<ApiResponse<Track | null>>(
        `${BASE}/${trackId}/restore`,
        {},
      );
      return res.data;
    },
    onSuccess: () => invalidateTrackDependents(qc),
  });
}

export function useAdminScope() {
  return useQuery({
    queryKey: ["admin-scope"],
    queryFn: async () => {
      const res = await myFetch.get<ApiResponse<AdminScope>>("/auth/scope");
      return res.data.data;
    },
    staleTime: 5 * 60 * 1000,
  });
}
