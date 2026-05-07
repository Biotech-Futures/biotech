export type ResourceRole = {
  id: number;
  slug: string;
  name?: string;
};

export type ResourceTypeName = "document" | "guide" | "video" | "template";
export type ResourceKind = "file" | "page";
export type ResourceOrder = "newest" | "oldest";
export type VisibilityScope = "global" | "track_based" | "role_based";

export type ResourceTypeOption = {
  value: ResourceTypeName;
  label: string;
};

export type ResourceUploader = {
  id: string | number;
  first_name: string;
  last_name: string;
  email: string;
};

export type ResourceAudience = {
  id: number;
  resource_id: number;
  role_id: number | null;
  track_id: number | null;
  role: ResourceRole | null;
};

export type ResourceTrackOption = {
  id: number;
  code: string;
  label: string;
};

export type Resource = {
  id: number;
  uploaded_by_id: string | number;
  track_id: number | null;
  group_id: number | null;
  visibility_scope: VisibilityScope;
  uploaded_at: string;
  deleted_at: string | null;
  kind: ResourceKind;
  name: string;
  description: string | null;
  type_name: ResourceTypeName | null;
  type_id: number | null;
  content_html: string | null;
  file_name: string | null;
  file_mime_type: string | null;
  file_size: number | null;
  storage_key: string;
  uploader: ResourceUploader;
  audiences: ResourceAudience[];
};

export type PaginatedResponse<T> = {
  msg: string;
  data: {
    items: T[];
    total: number;
    page: number;
    limit: number;
    hasMore: boolean;
  };
};

export const RESOURCE_TYPES: ResourceTypeOption[] = [
  { value: "document", label: "Document" },
  { value: "guide", label: "Guide" },
  { value: "video", label: "Video" },
  { value: "template", label: "Template" },
];

export const RESOURCE_TRACKS: ResourceTrackOption[] = [
  { id: 1, code: "AUS-NSW", label: "AUS-NSW (New South Wales)" },
  { id: 2, code: "AUS-QLD", label: "AUS-QLD (Queensland)" },
  { id: 3, code: "AUS-VIC", label: "AUS-VIC (Victoria)" },
  { id: 4, code: "AUS-WA", label: "AUS-WA (Western Australia)" },
  { id: 5, code: "Brazil", label: "Brazil" },
  { id: 6, code: "Global", label: "Global" },
];

export function getResourceTrackLabel(trackId: number | null | undefined): string {
  if (trackId === null || trackId === undefined) return "Unassigned";
  return `ID:${trackId}`;
}

export function getResourceTypeLabel(typeName: ResourceTypeName | null | undefined): string {
  if (!typeName) return "Uncategorized";
  return RESOURCE_TYPES.find((item) => item.value === typeName)?.label ?? "Uncategorized";
}
