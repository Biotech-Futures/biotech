import { myFetch } from "@/lib/myFetch";
import {
  confirmAssignmentsResponseSchema,
  individualStudentsResponseSchema,
  matchRecommendationsResponseSchema,
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

export function useQueryIndividualStudents() {
  return useQuery({
    queryKey: ["individualStudents"],
    queryFn: async () => {
      const res = await myFetch.get("match/individual");
      return individualStudentsResponseSchema.parse(res.data);
    },
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
