import { useQuery } from "@tanstack/react-query";
import { myFetch } from "@/lib/myFetch";
import type {
  StudentPaginatedResponse,
  StudentTrack,
  TracksResponse,
} from "@/type/user";

interface QueryStudentsParams {
  page: number;
  limit?: number;
  search?: string;
  track?: StudentTrack;
  inGroup?: "yes" | "no";
}

export function useQueryStudents(params: QueryStudentsParams) {
  const { page, limit = 10, search, track, inGroup } = params;

  return useQuery({
    queryKey: ["students", page, limit, search, track, inGroup],
    queryFn: async (): Promise<StudentPaginatedResponse> => {
      const res = await myFetch.get<StudentPaginatedResponse>("/user", {
        params: {
          page,
          limit,
          search,
          role: "student",
          track,
          inGroup,
        },
      });
      return res.data;
    },
  });
}

export function useQueryTracks() {
  return useQuery({
    queryKey: ["tracks"],
    queryFn: async (): Promise<TracksResponse> => {
      const res = await myFetch.get<TracksResponse>("/user/tracks");
      return res.data;
    },
  });
}

export function useQueryHasUngroupedStudents() {
  return useQuery({
    queryKey: ["hasUngroupedStudents"],
    queryFn: async (): Promise<{ msg: string; data: { hasUngrouped: boolean } }> => {
      const res = await myFetch.get<{ msg: string; data: { hasUngrouped: boolean } }>("/user/ungrouped-check");
      return res.data;
    },
  });
}
