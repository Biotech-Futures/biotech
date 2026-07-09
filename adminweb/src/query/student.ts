import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { myFetch } from "@/lib/myFetch";
import type { StudentPaginatedResponse } from "@/type/user";
import type { StudentImportRow } from "@/query/user";

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

/** Bulk-import students from a parsed registration export (POST /user/bulk). */
export function useImportStudents() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (rows: StudentImportRow[]) => {
      const payload = rows.map((row) => ({
        firstName: row.firstName,
        lastName: row.lastName,
        email: row.email,
        role: "student" as const,
        state: row.state,
        country: row.country,
        schoolName: row.schoolName,
        yearLevel: row.yearLevel,
        interests: row.interests,
        guardianFirstName: row.guardianFirstName,
        guardianLastName: row.guardianLastName,
        guardianEmail: row.guardianEmail || undefined,
        supervisorFirstName: row.supervisorFirstName,
        supervisorLastName: row.supervisorLastName,
        // Omit when blank so the backend leaves the supervisor link untouched.
        supervisorEmail: row.supervisorEmail || undefined,
        joinpermResponseId: row.joinpermResponseId,
        active: row.active,
      }));
      const res = await myFetch.post<{
        msg: string;
        data: {
          created: unknown[];
          skipped: { email: string; reason: string }[];
        };
      }>("/user/bulk", payload);
      return res.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["students"] });
      void queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });
}
