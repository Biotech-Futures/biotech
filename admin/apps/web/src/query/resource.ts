import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { myFetch } from "@/lib/myFetch";
import type { CreateResource, UpdateResource } from "@/schema/resource";
import type {
  Resource,
  ResourceKind,
  ResourceRole,
  ResourceTrackOption,
  ResourceOrder,
  ResourceTypeOption,
  ResourceTypeName,
  PaginatedResponse,
} from "@/type/resource";

interface QueryResourcesParams {
  page: number;
  search?: string;
  uploader?: string;
  track_id?: number;
  order?: ResourceOrder;
  resource_type?: ResourceTypeName;
  resource_kind?: ResourceKind;
}

export function useQueryResources(params: QueryResourcesParams) {
  const { page, search, uploader, track_id, order, resource_type, resource_kind } = params;

  return useQuery({
    queryKey: ["resources", page, search, uploader, track_id, order, resource_type, resource_kind],
    queryFn: async (): Promise<PaginatedResponse<Resource>> => {
      const res = await myFetch.get<PaginatedResponse<Resource>>("/resource", {
        params: {
          page,
          search,
          uploader,
          track_id,
          resource_type,
          resource_kind,
          order: order ?? "newest",
        },
      });
      return res.data;
    },
  });
}

export function useQueryResource(id: number | null) {
  return useQuery({
    queryKey: ["resource", id],
    queryFn: async () => {
      const res = await myFetch.get<{ msg: string; data: Resource | null }>(`/resource/${id}`);
      return res.data;
    },
    enabled: id !== null,
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
      const res = await myFetch.get<{ msg: string; data: ResourceTypeOption[] }>("/resource/types");
      return res.data;
    },
  });
}

export function useQueryResourceTracks() {
  return useQuery({
    queryKey: ["resource-tracks"],
    queryFn: async () => {
      const res = await myFetch.get<{ msg: string; data: ResourceTrackOption[] }>(
        "/resource/tracks",
      );
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

export function useUploadResource() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: FormData) => {
      const res = await myFetch.post<{ msg: string; data: Resource }>("/resource/upload", payload);
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
    mutationFn: async (data: { id: number; updates: UpdateResource }) => {
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
    mutationFn: async (id: number) => {
      const res = await myFetch.delete<{ msg: string; data: null }>(`/resource/${id}`);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["resources"] });
    },
  });
}

export async function downloadResourceFile(id: number, fallbackName?: string) {
  const res = await myFetch.get<Blob>(`/resource/${id}/download`, {
    responseType: "blob",
  });

  const disposition = String(res.headers["content-disposition"] ?? "");
  const fileNameFromHeader = disposition.match(/filename="?([^\"]+)"?/)?.[1];
  const fileName = decodeURIComponent(fileNameFromHeader || fallbackName || `resource-${id}`);

  const url = window.URL.createObjectURL(res.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
