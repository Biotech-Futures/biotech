import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { myFetch } from "@/lib/myFetch";
import type { Group, Track, PaginatedResponse } from "@/type/group";

interface QueryGroupsParams {
  page: number;
  searchName?: string;
  searchGroup?: string;
  track?: Track;
}

export function useQueryGroups(params: QueryGroupsParams) {
  const { page, searchName, searchGroup, track } = params;
  return useQuery({
    queryKey: ["groups", page, searchName, searchGroup, track],
    queryFn: async (): Promise<PaginatedResponse<Group>> => {
      const res = await myFetch.get<PaginatedResponse<Group>>(`/group`, {
        params: {
          page,
          searchName,
          searchGroup,
          track,
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
