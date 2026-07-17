import { myFetch } from "@/lib/myFetch";
import {
  confirmAssignmentsResponseSchema,
  matchRecommendationsResponseSchema,
  studentSuggestionsResponseSchema,
} from "@/schema/match";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AxiosError } from "axios";
import { toast } from "sonner";

export function useQueryMatchInfo() {
  return useQuery({
    queryKey: ["matchInfo"],
    queryFn: async () => {
      const res = await myFetch.get("match/student");
      return matchRecommendationsResponseSchema.parse(res.data);
    },
    enabled: false,
  });
}

/** Scored standalone students to fill a seat in the given group (best-first). */
export function useQueryStudentSuggestions(
  groupId: number | null,
  enabled = true,
) {
  return useQuery({
    queryKey: ["studentSuggestions", groupId],
    queryFn: async () => {
      const res = await myFetch.get(
        `match/student-suggestions?groupId=${groupId}`,
      );
      return studentSuggestionsResponseSchema.parse(res.data);
    },
    enabled: enabled && groupId != null,
  });
}

type ConfirmAssignmentPayload = {
  assignments: Array<{
    studentId: number;
    groupId: number | string;
  }>;
};

export function useMutationConfirmAssignments() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: ConfirmAssignmentPayload) => {
      const res = await myFetch.post("match/confirm", payload);
      return confirmAssignmentsResponseSchema.parse(res.data);
    },
    onSuccess: async (data) => {
      toast.success(
        `Confirmed ${data.data.assignedCount} student assignment${data.data.assignedCount === 1 ? "" : "s"}.`,
      );
      Promise.all([
        queryClient.invalidateQueries({ queryKey: ["students"] }),
        queryClient.invalidateQueries({ queryKey: ["groups"] }),
        queryClient.invalidateQueries({ queryKey: ["matchInfo"] }),
        queryClient.invalidateQueries({
          queryKey: ["individualStudents"],
        }),
      ]);
    },
    onError: (error) => {
      if (error instanceof AxiosError) {
        const msg =
          (error.response?.data as { msg?: string } | undefined)?.msg ??
          error.message;
        toast.error(`Assignment failed: ${msg}`);
      } else {
        toast.error("Assignment failed. Please try again.");
      }
    },
  });
}
