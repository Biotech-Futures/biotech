export type ResourceRole = {
  id: string;
  role_name: string;
};

export type ResourceTypeName = "document" | "guide" | "video" | "template";

export type ResourceType = {
  id: string;
  type_name: ResourceTypeName;
  type_description: string;
};

export type ResourceUploader = {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
};

export type Resource = {
  id: string;
  resource_name: string;
  resource_description: string;
  resource_type_detail: ResourceType | null;
  upload_datetime: string;
  uploader: ResourceUploader;
  visible_roles: ResourceRole[];
  deleted_flag: boolean;
  deleted_datetime: string | null;
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

export const RESOURCE_TYPES: ResourceTypeName[] = [
  "document",
  "guide",
  "video",
  "template",
];
