import { myFetch } from "@/lib/myFetch";
import {
  confirmMentorAssignmentsResponseSchema,
  mentorMatchResponseSchema,
  unmatchedGroupsResponseSchema,
} from "@/schema/mentorMatch";
import { useMutation, useQuery } from "@tanstack/react-query";

export type MatchMode = "balanced" | "strict" | "coverage";

export function useQueryMentorMatchInfo(mode: MatchMode = "balanced") {
  return useQuery({
    queryKey: ["mentorMatchInfo", mode],
    queryFn: async () => {
      const res = await myFetch.get(`mentor-match/recommend?mode=${mode}`);
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
  assignments: Array<{ groupId: number; mentorUserId: number }>;
};

export function useMutationConfirmMentorAssignments() {
  return useMutation({
    mutationFn: async (payload: ConfirmMentorAssignmentPayload) => {
      const res = await myFetch.post("mentor-match/confirm", payload);
      return confirmMentorAssignmentsResponseSchema.parse(res.data);
    },
  });
}
