import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { myFetch } from "@/lib/myFetch";
import type {
  AdminTaskListResponse,
  Task,
  TaskCreateValues,
  TaskFanoutResult,
  TaskUpdateValues,
} from "@/type/task";

const QUERY_KEY = "tasks";

export function useQueryTasks(params: {
  page?: number;
  limit?: number;
  task_type?: string;
  sortBy?: "completed" | "name" | "type" | "target" | "status" | "due" | "createdAt";
  sortOrder?: "asc" | "desc";
}) {
  return useQuery({
    queryKey: [QUERY_KEY, params],
    queryFn: async () => {
      const res = await myFetch.get<AdminTaskListResponse>("/task/", {
        params: {
          page: params.page ?? 1,
          limit: params.limit ?? 10,
          sortBy: params.sortBy,
          sortOrder: params.sortOrder,
          ...(params.task_type ? { task_type: params.task_type } : {}),
        },
      });
      return res.data;
    },
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}

export function useRoleRecipientCount(role: string) {
  return useQuery({
    queryKey: [QUERY_KEY, "role-recipients", role],
    queryFn: async () => {
      const res = await myFetch.get<{
        msg: string;
        data: { role: string; count: number } | null;
      }>("/task/role-recipients/", { params: { role } });
      return res.data;
    },
    enabled: Boolean(role),
  });
}

export function useCreateTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: TaskCreateValues) => {
      const res = await myFetch.post<{
        msg: string;
        data: Task | TaskFanoutResult;
      }>("/task/", data);
      return res.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [QUERY_KEY] });
    },
  });
}

export function useUpdateTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, updates }: { id: number; updates: TaskUpdateValues }) => {
      const res = await myFetch.patch<{ msg: string; data: Task }>(`/task/${id}/`, updates);
      return res.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [QUERY_KEY] });
    },
  });
}

export function useDeleteTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      await myFetch.delete(`/task/${id}/`);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [QUERY_KEY] });
    },
  });
}
