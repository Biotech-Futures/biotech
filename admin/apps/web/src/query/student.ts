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
  yearLevel?: number;
  track?: StudentTrack;
  interest?: string;
  inGroup?: "yes" | "no";
}

export function useQueryStudents(params: QueryStudentsParams) {
  const { page, limit = 10, search, yearLevel, track, interest, inGroup } =
    params;

  return useQuery({
    queryKey: [
      "students",
      page,
      limit,
      search,
      yearLevel,
      track,
      interest,
      inGroup,
    ],
    queryFn: async (): Promise<StudentPaginatedResponse> => {
      const res = await myFetch.get<StudentPaginatedResponse>("/user/students", {
        params: {
          page,
          limit,
          search,
          age: yearLevel,
          track,
          interest,
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
