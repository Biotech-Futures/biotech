import { myFetch } from "@/lib/myFetch";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { CreateUser, UpdateUser } from "@/schema/user";
import type { PaginatedResponse, Role, Track, User } from "@/type/user";

type QueryUsersParams = {
  page: number;
  search?: string;
  role?: Role;
  track?: Track;
};

export function useQueryUsers(params: QueryUsersParams) {
  const { page, search, role, track } = params;

  return useQuery({
    queryKey: ["users", page, search, role, track],
    queryFn: async (): Promise<PaginatedResponse<User>> => {
      const res = await myFetch.get<PaginatedResponse<User>>("/user", {
        params: {
          page,
          limit: 10,
          search,
          role,
          track,
        },
      });
      return res.data;
    },
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: CreateUser) => {
      const body = {
        ...payload,
        track: payload.track ?? undefined,
        groupId: payload.groupId ?? undefined,
      };
      const res = await myFetch.post<{ msg: string; data: User | null }>("/user", body);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: { id: string; updates: UpdateUser }) => {
      const body = {
        ...payload.updates,
        track: payload.updates.track ?? null,
        groupId: payload.updates.groupId ?? null,
      };
      const res = await myFetch.put<{ msg: string; data: User | null }>(
        `/user/${payload.id}`,
        body,
      );
      return res.data;
    },
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      queryClient.invalidateQueries({ queryKey: ["user", id] });
    },
  });
}

export function useDeleteUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      const res = await myFetch.delete<{ msg: string; data: null }>(`/user/${id}`);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });
}
