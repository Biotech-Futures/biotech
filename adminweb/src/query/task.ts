import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { myFetch } from "@/lib/myFetch";
import type {
  AdminTaskListResponse,
  Task,
  TaskCreateValues,
  TaskUpdateValues,
} from "@/type/task";

const QUERY_KEY = "tasks";

export function useQueryTasks(params: {
  page?: number;
  limit?: number;
  task_type?: string;
  deleted?: boolean;
}) {
  return useQuery({
    queryKey: [QUERY_KEY, params],
    queryFn: async () => {
      const res = await myFetch.get<AdminTaskListResponse>("/task/", {
        params: {
          page: params.page ?? 1,
          limit: params.limit ?? 10,
          ...(params.task_type ? { task_type: params.task_type } : {}),
          ...(params.deleted !== undefined ? { deleted: params.deleted } : {}),
        },
      });
      return res.data;
    },
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
}

export function useCreateTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: TaskCreateValues) => {
      const res = await myFetch.post<{ msg: string; data: Task }>("/task/", data);
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

export function useRestoreTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      const res = await myFetch.post<{ msg: string; data: Task | null }>(
        `/task/${id}/restore/`,
      );
      return res.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [QUERY_KEY] });
    },
  });
}

export function useToggleTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, completed }: { id: number; completed: boolean }) => {
      const res = await myFetch.post<{ msg: string; data: Task }>(
        `/task/${id}/toggle/`,
        { completed },
      );
      return res.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [QUERY_KEY] });
    },
  });
}
