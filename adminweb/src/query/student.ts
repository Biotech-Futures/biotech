import { useQuery } from "@tanstack/react-query";
import { myFetch } from "@/lib/myFetch";
import type { StudentPaginatedResponse } from "@/type/user";

export interface StudentStateOption {
  id: number;
  stateName: string;
  countryName: string | null;
}

export interface StudentStatesResponse {
  msg: string;
  data: StudentStateOption[];
}

interface QueryStudentsParams {
  page: number;
  limit?: number;
  search?: string;
  state?: string;
  inGroup?: "yes" | "no";
  sortBy?: "name" | "email" | "state" | "status" | "school" | "yearLevel" | "group" | "createdAt";
  sortOrder?: "asc" | "desc";
}

export function useQueryStudents(params: QueryStudentsParams) {
  const { page, limit = 10, search, state, inGroup, sortBy, sortOrder } = params;

  return useQuery({
    queryKey: ["students", page, limit, search, state, inGroup, sortBy, sortOrder],
    queryFn: async (): Promise<StudentPaginatedResponse> => {
      const res = await myFetch.get<StudentPaginatedResponse>("/user", {
        params: {
          page,
          limit,
          search,
          role: "student",
          state,
          inGroup,
          sortBy,
          sortOrder,
        },
      });
      return res.data;
    },
  });
}

export function useQueryStates() {
  return useQuery({
    queryKey: ["user-states"],
    queryFn: async (): Promise<StudentStatesResponse> => {
      const res = await myFetch.get<StudentStatesResponse>("/user/states");
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
