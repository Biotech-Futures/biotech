import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { myFetch } from "@/lib/myFetch";
import type { CreateResource, UpdateResource } from "@/schema/resource";
import type {
  Resource,
  ResourceKind,
  ResourceRole,
  ResourceTrackOption,
  ResourceOrder,
  ResourceAccess,
  ResourceTypeOption,
  ResourceTypeName,
  PaginatedResponse,
} from "@/type/resource";
import { buildUrl } from "@/util/url";

type ApiResource = Partial<Resource> & {
  id: number | string;
  resource_name?: string;
  resource_description?: string | null;
  resource_kind?: Resource["kind"];
  resource_type?: Resource["type_name"];
  resource_type_id?: number | string | null;
  uploader_user_id?: string | number;
  name?: string;
  description?: string | null;
  kind?: Resource["kind"];
  uploaded_by_id?: string | number;
  type_id?: number | string | null;
  group_id?: number | string | null;
};

function toNullableNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function normalizeResource(resource: ApiResource): Resource {
  const storageKey = resource.storage_key ?? "";
  const inferredFileName =
    storageKey && storageKey.includes("/")
      ? decodeURIComponent(storageKey.split("/").pop() ?? "")
      : null;

  const uploader = resource.uploader ?? {
    id: resource.uploader_user_id ?? resource.uploaded_by_id ?? "unknown",
    first_name: "Unknown",
    last_name: "User",
    email: "unknown@example.com",
  };

  const audiences = (resource.audiences ?? []).map((audience) => ({
    ...audience,
    role:
      audience.role && !audience.role.slug && audience.role.name
        ? {
            ...audience.role,
            slug: audience.role.name.toLowerCase().replace(/\s+/g, "-"),
          }
        : audience.role,
  }));

  return {
    id: Number(resource.id),
    uploader,
    audiences,
    uploaded_by_id:
      resource.uploaded_by_id ?? resource.uploader_user_id ?? "unknown",
    name: resource.name ?? resource.resource_name ?? "",
    description: resource.description ?? resource.resource_description ?? null,
    kind: resource.kind ?? resource.resource_kind ?? "file",
    type_name: resource.type_name ?? resource.resource_type ?? null,
    type_id: toNullableNumber(resource.type_id ?? resource.resource_type_id),
    group_id: toNullableNumber(resource.group_id),
    track_id: toNullableNumber(resource.track_id),
    visibility_scope: resource.visibility_scope ?? "global",
    uploaded_at: resource.uploaded_at ?? "",
    deleted_at: resource.deleted_at ?? null,
    content_html: resource.content_html ?? null,
    file_name: resource.file_name ?? inferredFileName,
    file_mime_type: resource.file_mime_type ?? null,
    file_size: resource.file_size ?? null,
    storage_key: resource.storage_key ?? "",
    labels: resource.labels ?? [],
  };
}

function normalizePaginatedResources(
  payload: PaginatedResponse<ApiResource>,
): PaginatedResponse<Resource> {
  return {
    ...payload,
    data: {
      ...payload.data,
      items: payload.data.items.map(normalizeResource),
    },
  };
}

interface QueryResourcesParams {
  page: number;
  search?: string;
  uploader?: string;
  track_id?: number;
  order?: ResourceOrder;
  resource_type?: ResourceTypeName;
  resource_kind?: ResourceKind;
  sortBy?: "name" | "type_name" | "visibility" | "role" | "track" | "uploader" | "uploaded_at";
  sortOrder?: "asc" | "desc";
}

export function useQueryResources(params: QueryResourcesParams) {
  const {
    page,
    search,
    uploader,
    track_id,
    order,
    resource_type,
    resource_kind,
    sortBy,
    sortOrder,
  } = params;

  return useQuery({
    queryKey: [
      "resources",
      page,
      search,
      uploader,
      track_id,
      order,
      resource_type,
      resource_kind,
      sortBy,
      sortOrder,
    ],
    queryFn: async (): Promise<PaginatedResponse<Resource>> => {
      const res = await myFetch.get<PaginatedResponse<ApiResource>>(
        "/resource",
        {
          params: {
            page,
            search,
            uploader,
            track_id,
            resource_type,
            resource_kind,
            order: order ?? "newest",
            sortBy,
            sortOrder,
          },
        },
      );
      return normalizePaginatedResources(res.data);
    },
  });
}

export function useQueryResource(id: number | null) {
  return useQuery({
    queryKey: ["resource", id],
    queryFn: async () => {
      const res = await myFetch.get<{ msg: string; data: ApiResource | null }>(
        `/resource/${id}`,
      );
      return {
        ...res.data,
        data: res.data.data ? normalizeResource(res.data.data) : null,
      };
    },
    enabled: id !== null,
  });
}

export function useQueryResourceRoles() {
  return useQuery({
    queryKey: ["resource-roles"],
    queryFn: async () => {
      const res = await myFetch.get<{ msg: string; data: ResourceRole[] }>(
        "/resource/roles",
      );
      return res.data;
    },
  });
}

export function useQueryResourceTypes() {
  return useQuery({
    queryKey: ["resource-types"],
    queryFn: async () => {
      const res = await myFetch.get<{
        msg: string;
        data: ResourceTypeOption[];
      }>("/resource/types");
      return res.data;
    },
  });
}

export function useQueryResourceTracks() {
  return useQuery({
    queryKey: ["resource-tracks"],
    queryFn: async () => {
      const res = await myFetch.get<{
        msg: string;
        data: ResourceTrackOption[];
      }>("/resource/tracks");
      return res.data;
    },
  });
}

export function useCreateResource() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: CreateResource) => {
      const res = await myFetch.post<{ msg: string; data: Resource }>(
        "/resource",
        payload,
      );
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
      const res = await myFetch.post<{ msg: string; data: Resource }>(
        "/resource/upload",
        payload,
      );
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

export function useReplaceResourceFile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: { id: number; payload: FormData }) => {
      const res = await myFetch.post<{ msg: string; data: Resource | null }>(
        `/resource/${data.id}/upload`,
        data.payload,
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
      const res = await myFetch.delete<{ msg: string; data: null }>(
        `/resource/${id}`,
      );
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["resources"] });
    },
  });
}

export type UploadedResourceLink = {
  id: number;
  fileName: string;
  kind?: ResourceKind;
  url: string;
  accessUrl?: string;
  downloadUrl?: string;
  mimeType: string | null;
  size: number | null;
};

export async function uploadLinkedResourceFile(
  file: File,
): Promise<UploadedResourceLink> {
  const payload = new FormData();
  payload.append("file", file);
  payload.append("resource_kind", "attachment");
  payload.append("resource_name", file.name);
  payload.append("resource_description", `Resource attachment: ${file.name}`);

  const res = await myFetch.post<{
    msg: string;
    data: ApiResource;
  }>("/resource/upload/", payload);

  const attachment = normalizeResource(res.data.data);
  const apiUrl = import.meta.env.VITE_PUBLIC_API_URL || "http://localhost:8000";
  const accessUrl = buildUrl(
    apiUrl,
    "api",
    "v1",
    "admin",
    "resource",
    String(attachment.id),
    "access",
  );
  return {
    id: attachment.id,
    kind: attachment.kind ?? "attachment",
    fileName: attachment.file_name ?? file.name,
    url: accessUrl,
    accessUrl,
    downloadUrl: buildUrl(
      apiUrl,
      "api",
      "v1",
      "admin",
      "resource",
      String(attachment.id),
      "download",
    ),
    mimeType: attachment.file_mime_type,
    size: attachment.file_size,
  };
}

export async function downloadResourceFile(id: number, fallbackName?: string) {
  const res = await myFetch.get<Blob>(`/resource/${id}/download`, {
    responseType: "blob",
  });

  const disposition = String(res.headers["content-disposition"] ?? "");
  const fileNameFromHeader = disposition.match(/filename="?([^\"]+)"?/)?.[1];
  const fileName = decodeURIComponent(
    fileNameFromHeader || fallbackName || `resource-${id}`,
  );

  const url = window.URL.createObjectURL(res.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export async function accessResourceFile(id: number): Promise<ResourceAccess> {
  const res = await myFetch.get<{ msg: string; data: ResourceAccess }>(
    `/resource/${id}/access`,
  );
  return res.data.data;
}

export function openResourceAccess(access: ResourceAccess) {
  if (access.temporary_url) {
    window.open(access.temporary_url, "_blank", "noopener,noreferrer");
    return;
  }

  if (access.content !== null) {
    const blob = new Blob([access.content], {
      type: access.mime_type || "text/plain",
    });
    const url = window.URL.createObjectURL(blob);
    window.open(url, "_blank", "noopener,noreferrer");
    window.setTimeout(() => window.URL.revokeObjectURL(url), 60_000);
  }
}
