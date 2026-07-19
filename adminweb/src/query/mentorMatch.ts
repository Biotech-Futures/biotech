import { myFetch } from "@/lib/myFetch";
import {
  confirmMentorAssignmentsResponseSchema,
  matchedGroupsResponseSchema,
  mentorListResponseSchema,
  mentorMatchResponseSchema,
  mentorReplaceSuggestionsResponseSchema,
  replaceMentorResponseSchema,
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
    refetchOnMount: true,
  });
}

export function useQueryMentorList() {
  return useQuery({
    queryKey: ["mentorList"],
    queryFn: async () => {
      const res = await myFetch.get("mentor-match/mentors");
      return mentorListResponseSchema.parse(res.data);
    },
    // Capacity shifts as assignments are confirmed on either matching tab.
    refetchOnMount: true,
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

export function useQueryMatchedGroups() {
  return useQuery({
    queryKey: ["matchedGroups"],
    queryFn: async () => {
      const res = await myFetch.get("mentor-match/matched-groups");
      return matchedGroupsResponseSchema.parse(res.data);
    },
    refetchOnMount: true,
  });
}

/** Scored replacement-mentor suggestions for one group (best-first). */
export function useQueryMentorReplaceSuggestions(
  groupId: number | null,
  enabled = true,
) {
  return useQuery({
    queryKey: ["mentorReplaceSuggestions", groupId],
    queryFn: async () => {
      const res = await myFetch.get(
        `mentor-match/replace-suggestions?groupId=${groupId}`,
      );
      return mentorReplaceSuggestionsResponseSchema.parse(res.data);
    },
    enabled: enabled && groupId != null,
  });
}

type ReplaceMentorPayload = {
  membershipId: number;
  groupId: number;
  newMentorUserId: number;
};

export function useMutationReplaceMentor() {
  return useMutation({
    mutationFn: async (payload: ReplaceMentorPayload) => {
      const res = await myFetch.post("mentor-match/replace", payload);
      return replaceMentorResponseSchema.parse(res.data);
    },
  });
}

export function useMutationUnassignMentors() {
  return useMutation({
    mutationFn: async (groupIds: number[]) => {
      const res = await myFetch.post("mentor-match/unassign", { groupIds });
      return res.data as { msg: string; data: { unassignedCount: number } };
    },
  });
}
