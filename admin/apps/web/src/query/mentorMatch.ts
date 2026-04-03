import { myFetch } from "@/lib/myFetch";
import {
  confirmMentorAssignmentsResponseSchema,
  mentorMatchResponseSchema,
  unmatchedGroupsResponseSchema,
} from "@/schema/mentorMatch";
import { useMutation, useQuery } from "@tanstack/react-query";

export function useQueryMentorMatchInfo() {
  return useQuery({
    queryKey: ["mentorMatchInfo"],
    queryFn: async () => {
      const res = await myFetch.get("mentor-match/recommend");
      return mentorMatchResponseSchema.parse(res.data);
    },
    enabled: false,
  });
}

export function useQueryUnmatchedGroups() {
  return useQuery({
    queryKey: ["unmatchedGroups"],
    queryFn: async () => {
      const res = await myFetch.get("mentor-match/groups");
      return unmatchedGroupsResponseSchema.parse(res.data);
    },
  });
}

type ConfirmMentorAssignmentPayload = {
  assignments: Array<{ recommendationId: number }>;
};

export function useMutationConfirmMentorAssignments() {
  return useMutation({
    mutationFn: async (payload: ConfirmMentorAssignmentPayload) => {
      const res = await myFetch.post("mentor-match/confirm", payload);
      return confirmMentorAssignmentsResponseSchema.parse(res.data);
    },
  });
}
