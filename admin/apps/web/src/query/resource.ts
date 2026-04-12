import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { myFetch } from "@/lib/myFetch";
import type { CreateResource, UpdateResource } from "@/schema/resource";
import type {
  Resource,
  ResourceRole,
  ResourceOrder,
  ResourceType,
  ResourceTypeName,
  PaginatedResponse,
} from "@/type/resource";

interface QueryResourcesParams {
  page: number;
  search?: string;
  uploader?: string;
  order?: ResourceOrder;
  type?: ResourceTypeName;
}

export function useQueryResources(params: QueryResourcesParams) {
  const { page, search, uploader, order, type } = params;

  return useQuery({
    queryKey: ["resources", page, search, uploader, order, type],
    queryFn: async (): Promise<PaginatedResponse<Resource>> => {
      const res = await myFetch.get<PaginatedResponse<Resource>>("/resource", {
        params: {
          page,
          search,
          uploader,
          type,
          order: order ?? "newest",
        },
      });
      return res.data;
    },
  });
}

export function useQueryResource(id: string) {
  return useQuery({
    queryKey: ["resource", id],
    queryFn: async () => {
      const res = await myFetch.get<{ msg: string; data: Resource | null }>(`/resource/${id}`);
      return res.data;
    },
    enabled: !!id,
  });
}

export function useQueryResourceRoles() {
  return useQuery({
    queryKey: ["resource-roles"],
    queryFn: async () => {
      const res = await myFetch.get<{ msg: string; data: ResourceRole[] }>("/resource/roles");
      return res.data;
    },
  });
}

export function useQueryResourceTypes() {
  return useQuery({
    queryKey: ["resource-types"],
    queryFn: async () => {
      const res = await myFetch.get<{ msg: string; data: ResourceType[] }>("/resource/types");
      return res.data;
    },
  });
}

export function useCreateResource() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: CreateResource) => {
      const res = await myFetch.post<{ msg: string; data: Resource }>("/resource", payload);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["resources"] });
    },
  });
}

export function useUpdateResource() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: { id: string; updates: UpdateResource }) => {
      const res = await myFetch.put<{ msg: string; data: Resource | null }>(
        `/resource/${data.id}`,
        data.updates,
      );
      return res.data;
    },
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ["resources"] });
      queryClient.invalidateQueries({ queryKey: ["resource", id] });
    },
  });
}

export function useDeleteResource() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      const res = await myFetch.delete<{ msg: string; data: null }>(`/resource/${id}`);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["resources"] });
    },
  });
}
