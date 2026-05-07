import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { myFetch } from "@/lib/myFetch";
import type {
  Group,
  GroupMessage,
  MentorStatusFilter,
  Track,
  PaginatedResponse,
} from "@/type/group";

interface QueryGroupsParams {
  page: number;
  limit?: number;
  searchName?: string;
  searchGroup?: string;
  track?: Track;
  mentorStatus?: MentorStatusFilter;
}

export function useQueryGroups(params: QueryGroupsParams) {
  const { page, limit = 10, searchName, searchGroup, track, mentorStatus } =
    params;
  return useQuery({
    queryKey: [
      "groups",
      page,
      limit,
      searchName,
      searchGroup,
      track,
      mentorStatus,
    ],
    queryFn: async (): Promise<PaginatedResponse<Group>> => {
      const res = await myFetch.get<PaginatedResponse<Group>>(`/group`, {
        params: {
          page,
          limit,
          searchName,
          searchGroup,
          track,
          mentorStatus,
        },
      });
      return res.data;
    },
  });
}

// Query single group by ID
export function useQueryGroup(id: string) {
  return useQuery({
    queryKey: ["group", id],
    queryFn: async () => {
      const res = await myFetch.get<{ msg: string; data: Group | null }>(
        `/group/${id}`,
      );
      return res.data;
    },
    enabled: !!id,
  });
}

interface QueryGroupMessagesParams {
  page?: number;
  limit?: number;
  enabled?: boolean;
}

export function useQueryGroupMessages(
  id: string,
  { page = 1, limit = 50, enabled = true }: QueryGroupMessagesParams = {},
) {
  return useQuery({
    queryKey: ["group", id, "messages", page, limit],
    queryFn: async (): Promise<PaginatedResponse<GroupMessage>> => {
      const res = await myFetch.get<PaginatedResponse<GroupMessage>>(
        `/group/${id}/messages`,
        {
          params: { page, limit },
        },
      );
      return res.data;
    },
    enabled: enabled && !!id,
  });
}

// Update group mutation
export function useUpdateGroup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: { id: string; updates: Partial<Group> }) => {
      const res = await myFetch.put<{ msg: string; data: Group | null }>(
        `/group/${data.id}`,
        data.updates,
      );
      return res.data;
    },
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ["groups"] });
      queryClient.invalidateQueries({ queryKey: ["group", id] });
    },
  });
}

export function useRemoveGroupMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: { groupId: string; userId: string }) => {
      const res = await myFetch.delete<{ msg: string; data: Group | null }>(
        `/group/${data.groupId}/members/${data.userId}`,
      );
      return res.data;
    },
    onSuccess: (_, { groupId }) => {
      queryClient.invalidateQueries({ queryKey: ["groups"] });
      queryClient.invalidateQueries({ queryKey: ["group", groupId] });
      queryClient.invalidateQueries({ queryKey: ["students"] });
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });
}

export function useRemoveGroupMessage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: { groupId: string; messageId: string }) => {
      const res = await myFetch.delete<{
        msg: string;
        data: { id: string; groupId: string } | null;
      }>(`/group/${data.groupId}/messages/${data.messageId}`);
      return res.data;
    },
    onSuccess: (_, { groupId }) => {
      queryClient.invalidateQueries({
        queryKey: ["group", groupId, "messages"],
      });
    },
  });
}
