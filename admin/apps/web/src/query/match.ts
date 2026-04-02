import { myFetch } from "@/lib/myFetch";
import {
  confirmAssignmentsResponseSchema,
  individualStudentsResponseSchema,
  matchRecommendationsResponseSchema,
} from "@/schema/match";
import { useMutation, useQuery } from "@tanstack/react-query";

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
    groupId: number;
  }>;
};

export function useMutationConfirmAssignments() {
  return useMutation({
    mutationFn: async (payload: ConfirmAssignmentPayload) => {
      const res = await myFetch.post("match/confirm", payload);
      return confirmAssignmentsResponseSchema.parse(res.data);
    },
  });
}
