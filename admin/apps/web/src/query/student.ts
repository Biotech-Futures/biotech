import { useQuery } from "@tanstack/react-query";
import { myFetch } from "@/lib/myFetch";
import type { StudentPaginatedResponse, StudentTrack } from "@/type/user";

interface QueryStudentsParams {
  page: number;
  limit?: number;
  search?: string;
  age?: number;
  track?: StudentTrack;
  interest?: string;
  inGroup?: "yes" | "no";
}

export function useQueryStudents(params: QueryStudentsParams) {
  const { page, limit = 10, search, age, track, interest, inGroup } = params;

  return useQuery({
    queryKey: ["students", page, limit, search, age, track, interest, inGroup],
    queryFn: async (): Promise<StudentPaginatedResponse> => {
      const res = await myFetch.get<StudentPaginatedResponse>("/user/students", {
        params: {
          page,
          limit,
          search,
          age,
          track,
          interest,
          inGroup,
        },
      });
      return res.data;
    },
  });
}
