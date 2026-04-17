import type {
  QueryResourcesInput,
  CreateResourceInput,
  UpdateResourceInput,
} from "./schema.js";

export type Role = {
  id: number;
  slug: string;
};

export type ResourceTypeName = "document" | "guide" | "video" | "template";

export type ResourceTypeOption = {
  value: ResourceTypeName;
  label: string;
};

export type ResourceUploader = {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
};

export type AuthUploader = {
  id: string;
  name?: string | null;
  email?: string | null;
};

export type ResourceRow = {
  id: number;
  uploader_user_id: number;
  track_id: number | null;
  visibility_scope: string;
  uploaded_at: string;
  deleted_at: string | null;
  resource_name: string;
  resource_description: string | null;
  resource_type: ResourceTypeName | null;
  file_name: string | null;
  file_mime_type: string | null;
  file_size: number | null;
  storage_key: string;
};

export type ResourceAudience = {
  id: number;
  resource_id: number;
  role_id: number | null;
  track_id: number | null;
  role: Role | null;
};

export type Resource = ResourceRow & {
  uploader: ResourceUploader;
  audiences: ResourceAudience[];
};

const roles: Role[] = [
  { id: 1, slug: "student" },
  { id: 2, slug: "mentor" },
  { id: 3, slug: "admin" },
];

const ADMIN_ROLE_ID = 3;

const resourceTypeOptions: ResourceTypeOption[] = [
  { value: "document", label: "Document" },
  { value: "guide", label: "Guide" },
  { value: "video", label: "Video" },
  { value: "template", label: "Template" },
];

const trackOptions = [
  { id: 1, code: "AUS-NSW" },
  { id: 2, code: "AUS-QLD" },
  { id: 3, code: "AUS-VIC" },
  { id: 4, code: "AUS-WA" },
  { id: 5, code: "Brazil" },
  { id: 6, code: "Global" },
];

const mockUsers: ResourceUploader[] = [
  { id: 101, first_name: "Amy", last_name: "Wong", email: "amy.wong@example.com" },
  { id: 102, first_name: "Lucas", last_name: "Chan", email: "lucas.chan@example.com" },
  { id: 103, first_name: "Priya", last_name: "Shah", email: "priya.shah@example.com" },
];

function toTitleWord(input: string): string {
  if (!input) return "";
  return input.charAt(0).toUpperCase() + input.slice(1).toLowerCase();
}

function parseNameParts(name?: string | null) {
  const full = (name || "").trim();
  if (!full) {
    return { first_name: "Admin", last_name: "User" };
  }

  const parts = full.split(/\s+/);
  return {
    first_name: parts[0] || "Admin",
    last_name: parts.slice(1).join(" ") || "User",
  };
}

let nextUserId = 1000;

function ensureUploaderFromAuth(authUploader?: AuthUploader): ResourceUploader {
  if (!authUploader) return mockUsers[0];

  if (authUploader.email) {
    const byEmail = mockUsers.find((item) => item.email.toLowerCase() === authUploader.email?.toLowerCase());
    if (byEmail) return byEmail;
  }

  const nameParts = parseNameParts(authUploader.name);
  const created: ResourceUploader = {
    id: nextUserId++,
    first_name: nameParts.first_name,
    last_name: nameParts.last_name,
    email: authUploader.email || `${nameParts.first_name.toLowerCase()}.${nameParts.last_name.toLowerCase()}@example.com`,
  };
  mockUsers.push(created);
  return created;
}

function getRoleById(roleId: number | null): Role | null {
  if (roleId === null) return null;
  return roles.find((item) => item.id === roleId) ?? null;
}

function normalizeRoleIds(roleIds: number[] = []): number[] {
  const filtered = roleIds.filter((roleId) => roles.some((item) => item.id === roleId));
  return Array.from(new Set([...filtered, ADMIN_ROLE_ID]));
}

function buildStorageKey(resourceId: number, fileName?: string | null) {
  const stamp = Date.now();
  const safeName = (fileName || "resource.bin").replace(/[^a-zA-Z0-9._-]/g, "_");
  return `resources/${stamp}-${resourceId}-${safeName}`;
}

const titleByType: Record<ResourceTypeName, string[]> = {
  document: ["Research Summary", "Policy Brief", "Assessment Rubric", "Program Handbook"],
  guide: ["Peer Review Guide", "Onboarding Guide", "Submission Guide", "Mentor Handbook"],
  video: ["Workshop Recording", "Demo Walkthrough", "Q&A Recording", "Orientation Video"],
  template: ["Project Proposal Template", "Weekly Report Template", "Slides Template", "Feedback Template"],
};

function buildTitle(typeName: ResourceTypeName, index: number): string {
  const labels = titleByType[typeName];
  return `${labels[index % labels.length]} ${index + 1}`;
}

function buildDescription(typeName: ResourceTypeName, index: number): string {
  return `${toTitleWord(typeName)} resource content (${index + 1}).`;
}

type ResourceAudienceRow = {
  id: number;
  resource_id: number;
  role_id: number | null;
  track_id: number | null;
};

let nextResourceId = 1;
let nextAudienceId = 1;

function createAudienceRows(resourceId: number, roleIds: number[] | undefined, trackId: number | null) {
  const normalized = normalizeRoleIds(roleIds);
  const rows: ResourceAudienceRow[] = normalized.map((roleId) => ({
    id: nextAudienceId++,
    resource_id: resourceId,
    role_id: roleId,
    track_id: trackId,
  }));
  return rows;
}

function generateMockResources() {
  const rows: ResourceRow[] = [];
  const audienceRows: ResourceAudienceRow[] = [];

  const studentRoleId = roles.find((role) => role.slug === "student")?.id ?? 1;
  const mentorRoleId = roles.find((role) => role.slug === "mentor")?.id ?? 2;

  const visibilitySets: number[][] = [
    [studentRoleId, mentorRoleId, ADMIN_ROLE_ID],
    [studentRoleId, ADMIN_ROLE_ID],
    [mentorRoleId, ADMIN_ROLE_ID],
    [ADMIN_ROLE_ID],
  ];

  const randomInt = (max: number) => Math.floor(Math.random() * max);
  const typeValues = resourceTypeOptions.map((item) => item.value);

  for (let i = 0; i < 48; i++) {
    const typeName = typeValues[randomInt(typeValues.length)] as ResourceTypeName;
    const uploader = mockUsers[randomInt(mockUsers.length)];
    const track = trackOptions[randomInt(trackOptions.length)];
    const daysAgo = randomInt(360);
    const created = new Date(Date.now() - daysAgo * 24 * 60 * 60 * 1000);
    created.setHours(8 + randomInt(11), randomInt(60), 0, 0);

    const id = nextResourceId++;
    const fileName = `${typeName}-${id}.pdf`;
    const storageKey = buildStorageKey(id, fileName);

    const row: ResourceRow = {
      id,
      uploader_user_id: uploader.id,
      track_id: track.id,
      visibility_scope: "role_based",
      uploaded_at: created.toISOString(),
      deleted_at: null,
      resource_name: buildTitle(typeName, i + randomInt(16)),
      resource_description: buildDescription(typeName, i + randomInt(16)),
      resource_type: typeName,
      file_name: fileName,
      file_mime_type: "application/pdf",
      file_size: 80_000 + randomInt(1_500_000),
      storage_key: storageKey,
    };

    rows.push(row);
    audienceRows.push(...createAudienceRows(id, visibilitySets[randomInt(visibilitySets.length)], track.id));
  }

  return { rows, audienceRows };
}

const initial = generateMockResources();
let mockResources: ResourceRow[] = initial.rows;
let mockResourceAudience: ResourceAudienceRow[] = initial.audienceRows;

const uploadedFiles = new Map<
  string,
  {
    file_name: string;
    mime_type: string;
    bytes: ArrayBuffer;
  }
>();

function buildResource(resourceRow: ResourceRow): Resource {
  const uploader = mockUsers.find((item) => item.id === resourceRow.uploader_user_id) ?? mockUsers[0];
  const audiences: ResourceAudience[] = mockResourceAudience
    .filter((item) => item.resource_id === resourceRow.id)
    .map((item) => ({
      id: item.id,
      resource_id: item.resource_id,
      role_id: item.role_id,
      track_id: item.track_id,
      role: getRoleById(item.role_id),
    }));

  return {
    ...resourceRow,
    uploader,
    audiences,
  };
}

export function queryResources(params: QueryResourcesInput) {
  const { page, limit, search, uploader, uploader_user_id, track_id, resource_type, role_slug, order } = params;
  const offset = (page - 1) * limit;

  let filteredRows = mockResources.filter((resource) => !resource.deleted_at);

  if (search) {
    const keyword = search.toLowerCase();
    filteredRows = filteredRows.filter((resource) =>
      resource.resource_name.toLowerCase().includes(keyword) ||
      (resource.resource_description || "").toLowerCase().includes(keyword),
    );
  }

  if (uploader) {
    const uploaderKeyword = uploader.toLowerCase();
    filteredRows = filteredRows.filter((resource) => {
      const person = mockUsers.find((item) => item.id === resource.uploader_user_id);
      if (!person) return false;
      const fullName = `${person.first_name} ${person.last_name}`.trim().toLowerCase();
      return fullName.includes(uploaderKeyword);
    });
  }

  if (uploader_user_id !== undefined) {
    filteredRows = filteredRows.filter((resource) => resource.uploader_user_id === uploader_user_id);
  }

  if (track_id !== undefined) {
    filteredRows = filteredRows.filter((resource) => resource.track_id === track_id);
  }

  if (resource_type) {
    filteredRows = filteredRows.filter((resource) => resource.resource_type === resource_type);
  }

  if (role_slug) {
    const keyword = role_slug.toLowerCase();
    filteredRows = filteredRows.filter((resource) => {
      const audiences = mockResourceAudience.filter((item) => item.resource_id === resource.id);
      return audiences.some((audience) => {
        const role = getRoleById(audience.role_id);
        return role ? role.slug.includes(keyword) : false;
      });
    });
  }

  filteredRows = filteredRows.sort((a, b) => {
    const at = new Date(a.uploaded_at).getTime();
    const bt = new Date(b.uploaded_at).getTime();
    return order === "oldest" ? at - bt : bt - at;
  });

  const total = filteredRows.length;
  const items = filteredRows.slice(offset, offset + limit).map(buildResource);

  return {
    msg: "Resources retrieved successfully",
    data: {
      items,
      total,
      page,
      limit,
      hasMore: offset + limit < total,
    },
  };
}

export function queryResourceById(id: number) {
  const row = mockResources.find((item) => item.id === id && !item.deleted_at) ?? null;
  if (!row) {
    return {
      msg: "Resource not found",
      data: null,
    };
  }

  return {
    msg: "Resource retrieved successfully",
    data: buildResource(row),
  };
}

export function createResource(payload: CreateResourceInput, authUploader?: AuthUploader) {
  const uploader = ensureUploaderFromAuth(authUploader);
  const id = nextResourceId++;

  const row: ResourceRow = {
    id,
    uploader_user_id: uploader.id,
    track_id: payload.track_id ?? trackOptions[0]?.id ?? null,
    visibility_scope: "role_based",
    uploaded_at: new Date().toISOString(),
    deleted_at: null,
    resource_name: payload.resource_name,
    resource_description: payload.resource_description,
    resource_type: payload.resource_type ?? null,
    file_name: null,
    file_mime_type: null,
    file_size: null,
    storage_key: buildStorageKey(id),
  };

  mockResources = [row, ...mockResources];
  mockResourceAudience = [
    ...createAudienceRows(id, payload.role_ids, row.track_id),
    ...mockResourceAudience,
  ];

  return {
    msg: "Resource created successfully",
    data: buildResource(row),
  };
}

export function uploadResource(payload: {
  resource_name: string;
  resource_description: string;
  resource_type?: ResourceTypeName;
  track_id?: number;
  role_ids?: number[];
  file_name: string;
  file_size: number;
  file_mime_type?: string;
  file_bytes: ArrayBuffer;
  uploader?: AuthUploader;
}) {
  const uploader = ensureUploaderFromAuth(payload.uploader);
  const id = nextResourceId++;
  const storageKey = buildStorageKey(id, payload.file_name);

  const row: ResourceRow = {
    id,
    uploader_user_id: uploader.id,
    track_id: payload.track_id ?? trackOptions[0]?.id ?? null,
    visibility_scope: "role_based",
    uploaded_at: new Date().toISOString(),
    deleted_at: null,
    resource_name: payload.resource_name,
    resource_description: payload.resource_description,
    resource_type: payload.resource_type ?? null,
    file_name: payload.file_name,
    file_mime_type: payload.file_mime_type || "application/octet-stream",
    file_size: payload.file_size,
    storage_key: storageKey,
  };

  mockResources = [row, ...mockResources];
  mockResourceAudience = [
    ...createAudienceRows(id, payload.role_ids, row.track_id),
    ...mockResourceAudience,
  ];

  uploadedFiles.set(storageKey, {
    file_name: payload.file_name,
    mime_type: payload.file_mime_type || "application/octet-stream",
    bytes: payload.file_bytes,
  });

  return {
    msg: "Resource uploaded successfully",
    data: buildResource(row),
  };
}

export function downloadResource(id: number) {
  const row = mockResources.find((item) => item.id === id && !item.deleted_at);
  if (!row) {
    return {
      msg: "Resource not found",
      data: null,
    } as const;
  }

  const file = uploadedFiles.get(row.storage_key);
  if (!file) {
    return {
      msg: "This resource has no uploaded file",
      data: null,
    } as const;
  }

  return {
    msg: "Resource download prepared",
    data: file,
  } as const;
}

export function updateResource(id: number, updates: UpdateResourceInput) {
  const index = mockResources.findIndex((item) => item.id === id && !item.deleted_at);
  if (index === -1) {
    return {
      msg: "Resource not found",
      data: null,
    };
  }

  const current = mockResources[index];
  const updated: ResourceRow = {
    ...current,
    resource_name: updates.resource_name ?? current.resource_name,
    resource_description: updates.resource_description ?? current.resource_description,
    resource_type: updates.resource_type === undefined ? current.resource_type : updates.resource_type,
    track_id: updates.track_id === undefined ? current.track_id : updates.track_id,
  };

  mockResources[index] = updated;

  if (updates.role_ids) {
    mockResourceAudience = mockResourceAudience.filter((item) => item.resource_id !== id);
    mockResourceAudience.push(...createAudienceRows(id, updates.role_ids, updated.track_id));
  }

  return {
    msg: "Resource updated successfully",
    data: buildResource(updated),
  };
}

export function deleteResource(id: number) {
  const index = mockResources.findIndex((item) => item.id === id && !item.deleted_at);
  if (index === -1) {
    return {
      msg: "Resource not found",
      data: null,
    };
  }

  mockResources[index] = {
    ...mockResources[index],
    deleted_at: new Date().toISOString(),
  };

  return {
    msg: "Resource deleted successfully",
    data: null,
  };
}

export function assignRoleToResource(id: number, roleId: number) {
  const resource = mockResources.find((item) => item.id === id && !item.deleted_at);
  if (!resource) {
    return {
      msg: "Resource not found",
      data: null,
    };
  }

  if (!roles.some((item) => item.id === roleId)) {
    return {
      msg: "Role not found",
      data: null,
    };
  }

  const exists = mockResourceAudience.some(
    (item) => item.resource_id === id && item.role_id === roleId,
  );

  if (!exists) {
    mockResourceAudience.push({
      id: nextAudienceId++,
      resource_id: id,
      role_id: roleId,
      track_id: resource.track_id,
    });
  }

  return {
    msg: "Role assigned successfully",
    data: buildResource(resource),
  };
}

export function removeRoleFromResource(id: number, roleId: number) {
  const resource = mockResources.find((item) => item.id === id && !item.deleted_at);
  if (!resource) {
    return {
      msg: "Resource not found",
      data: null,
    };
  }

  if (roleId === ADMIN_ROLE_ID) {
    return {
      msg: "Admin visibility is required and cannot be removed",
      data: buildResource(resource),
    };
  }

  mockResourceAudience = mockResourceAudience.filter(
    (item) => !(item.resource_id === id && item.role_id === roleId),
  );

  return {
    msg: "Role removed successfully",
    data: buildResource(resource),
  };
}

export function listResourceRoles() {
  return {
    msg: "Roles retrieved successfully",
    data: roles,
  };
}

export function listResourceTypes() {
  return {
    msg: "Resource types retrieved successfully",
    data: resourceTypeOptions,
  };
}
