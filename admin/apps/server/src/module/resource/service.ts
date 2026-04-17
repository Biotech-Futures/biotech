import db from "@/lib/db.js";
import {
  resources,
  resourceAudience,
  roles,
  users,
} from "@/drizzle/schema.js";
import {
  and,
  asc,
  desc,
  eq,
  inArray,
  isNull,
  sql,
} from "drizzle-orm";
import type {
  QueryResourcesInput,
  CreateResourceInput,
  UpdateResourceInput,
} from "./schema.js";
import {
  demoResourceAudience,
  demoResources,
  demoResourceTypes,
  demoRoles,
  demoUploaders,
  useResourceDemoData,
  type DemoResourceAudienceRow,
  type DemoResourceRow,
} from "./demo.js";

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

const ADMIN_ROLE_SLUG = "admin";
const FALLBACK_ROLES: Role[] = demoRoles.map((item) => ({ ...item }));
const FALLBACK_TYPES: ResourceTypeOption[] = demoResourceTypes.map((item) => ({ ...item }));
const FALLBACK_UPLOADERS: ResourceUploader[] = demoUploaders.map((item) => ({ ...item }));

let demoRows: DemoResourceRow[] = demoResources.map((item) => ({ ...item }));
let demoAudienceRows: DemoResourceAudienceRow[] = demoResourceAudience.map((item) => ({ ...item }));
let nextDemoResourceId = Math.max(0, ...demoRows.map((item) => item.id)) + 1;
let nextDemoAudienceId = Math.max(0, ...demoAudienceRows.map((item) => item.id)) + 1;

const uploadedFiles = new Map<
  string,
  {
    file_name: string;
    mime_type: string;
    bytes: ArrayBuffer;
  }
>();

type DbResourceExtra = {
  resource_name: string;
  resource_description: string | null;
  resource_type: ResourceTypeName | null;
  file_name: string | null;
  file_mime_type: string | null;
  file_size: number | null;
  storage_key: string;
};

const dbResourceExtras = new Map<number, DbResourceExtra>();

function getDbResourceExtra(id: number): DbResourceExtra {
  return (
    dbResourceExtras.get(id) ?? {
      resource_name: `Resource ${id}`,
      resource_description: null,
      resource_type: null,
      file_name: null,
      file_mime_type: null,
      file_size: null,
      storage_key: buildStorageKey(id),
    }
  );
}

function normalizeRoleIds(roleIds: number[] = [], availableRoles: Role[]): number[] {
  const adminRole = availableRoles.find((item) => item.slug === ADMIN_ROLE_SLUG);
  const validIds = roleIds.filter((roleId) => availableRoles.some((item) => item.id === roleId));
  const withAdmin = adminRole ? [...validIds, adminRole.id] : validIds;
  return Array.from(new Set(withAdmin));
}

function buildStorageKey(resourceId: number, fileName?: string | null) {
  const stamp = Date.now();
  const safeName = (fileName || "resource.bin").replace(/[^a-zA-Z0-9._-]/g, "_");
  return `resources/${stamp}-${resourceId}-${safeName}`;
}

function buildResourceFromDemoRow(resourceRow: DemoResourceRow): Resource {
  const uploader =
    FALLBACK_UPLOADERS.find((item) => item.id === resourceRow.uploader_user_id) ??
    FALLBACK_UPLOADERS[0];

  const audiences: ResourceAudience[] = demoAudienceRows
    .filter((item) => item.resource_id === resourceRow.id)
    .map((item) => {
      const role = FALLBACK_ROLES.find((r) => r.id === item.role_id) ?? null;
      return {
        id: item.id,
        resource_id: item.resource_id,
        role_id: item.role_id,
        track_id: item.track_id,
        role,
      };
    });

  return {
    ...resourceRow,
    uploader,
    audiences,
  };
}

async function getRolesFromDb(): Promise<Role[]> {
  const rows = await db
    .select({ id: roles.id, slug: roles.slug })
    .from(roles)
    .orderBy(asc(roles.id));

  if (!rows.length) return FALLBACK_ROLES;
  return rows.map((item) => ({ id: item.id, slug: item.slug }));
}

function parseName(name?: string | null) {
  const full = (name || "").trim();
  if (!full) return { first: "Admin", last: "User" };
  const parts = full.split(/\s+/);
  return {
    first: parts[0] || "Admin",
    last: parts.slice(1).join(" ") || "User",
  };
}

async function resolveUploaderForDb(authUploader?: AuthUploader): Promise<ResourceUploader> {
  if (authUploader?.email) {
    const matched = await db
      .select({
        id: users.id,
        first_name: users.firstName,
        last_name: users.lastName,
        email: users.email,
      })
      .from(users)
      .where(eq(users.email, authUploader.email))
      .limit(1);

    if (matched[0]) {
      return matched[0];
    }
  }

  const firstUser = await db
    .select({
      id: users.id,
      first_name: users.firstName,
      last_name: users.lastName,
      email: users.email,
    })
    .from(users)
    .orderBy(asc(users.id))
    .limit(1);

  if (firstUser[0]) {
    return firstUser[0];
  }

  const parsed = parseName(authUploader?.name);
  return {
    id: FALLBACK_UPLOADERS[0]?.id ?? 1,
    first_name: parsed.first,
    last_name: parsed.last,
    email: authUploader?.email || "admin@example.com",
  };
}

async function nextResourceIdFromDb() {
  const row = await db
    .select({ maxId: sql<number>`coalesce(max(${resources.id}), 0)` })
    .from(resources);
  return (row[0]?.maxId ?? 0) + 1;
}

async function nextAudienceIdFromDb() {
  const row = await db
    .select({ maxId: sql<number>`coalesce(max(${resourceAudience.id}), 0)` })
    .from(resourceAudience);
  return (row[0]?.maxId ?? 0) + 1;
}

async function fetchResourcesFromDbRows(params: QueryResourcesInput) {
  const conditions = [isNull(resources.deletedAt)];

  if (params.uploader_user_id !== undefined) {
    conditions.push(eq(resources.uploaderUserId, params.uploader_user_id));
  }

  if (params.track_id !== undefined) {
    conditions.push(eq(resources.trackId, params.track_id));
  }

  const rows = await db
    .select({
      id: resources.id,
      uploader_user_id: resources.uploaderUserId,
      track_id: resources.trackId,
      visibility_scope: resources.visibilityScope,
      uploaded_at: resources.uploadedAt,
      deleted_at: resources.deletedAt,
    })
    .from(resources)
    .where(and(...conditions))
    .orderBy(params.order === "oldest" ? asc(resources.uploadedAt) : desc(resources.uploadedAt));

  return rows.map((row) => {
    const extra = getDbResourceExtra(row.id);
    return {
      ...row,
      ...extra,
    };
  }) as ResourceRow[];
}

async function fetchResourceByIdFromDb(id: number): Promise<ResourceRow | null> {
  const row = await db
    .select({
      id: resources.id,
      uploader_user_id: resources.uploaderUserId,
      track_id: resources.trackId,
      visibility_scope: resources.visibilityScope,
      uploaded_at: resources.uploadedAt,
      deleted_at: resources.deletedAt,
    })
    .from(resources)
    .where(and(eq(resources.id, id), isNull(resources.deletedAt)))
    .limit(1);

  if (!row[0]) return null;
  const extra = getDbResourceExtra(row[0].id);
  return { ...row[0], ...extra } as ResourceRow;
}

async function hydrateDbResources(resourceRows: ResourceRow[]): Promise<Resource[]> {
  if (!resourceRows.length) return [];

  const uploaderIds = Array.from(new Set(resourceRows.map((item) => item.uploader_user_id)));
  const uploaderRows = await db
    .select({
      id: users.id,
      first_name: users.firstName,
      last_name: users.lastName,
      email: users.email,
    })
    .from(users)
    .where(inArray(users.id, uploaderIds));

  const uploaderMap = new Map(uploaderRows.map((item) => [item.id, item] as const));
  const resourceIds = resourceRows.map((item) => item.id);

  const audienceRows = await db
    .select({
      id: resourceAudience.id,
      resource_id: resourceAudience.resourceId,
      role_id: resourceAudience.roleId,
      track_id: resourceAudience.trackId,
      role_slug: roles.slug,
    })
    .from(resourceAudience)
    .leftJoin(roles, eq(resourceAudience.roleId, roles.id))
    .where(inArray(resourceAudience.resourceId, resourceIds));

  const audienceMap = new Map<number, ResourceAudience[]>();
  for (const row of audienceRows) {
    const existing = audienceMap.get(row.resource_id) ?? [];
    existing.push({
      id: row.id,
      resource_id: row.resource_id,
      role_id: row.role_id,
      track_id: row.track_id,
      role: row.role_id && row.role_slug ? { id: row.role_id, slug: row.role_slug } : null,
    });
    audienceMap.set(row.resource_id, existing);
  }

  return resourceRows.map((row) => ({
    ...row,
    uploader:
      uploaderMap.get(row.uploader_user_id) ?? {
        id: row.uploader_user_id,
        first_name: "Unknown",
        last_name: "User",
        email: "unknown@example.com",
      },
    audiences: audienceMap.get(row.id) ?? [],
  }));
}

export async function queryResources(params: QueryResourcesInput) {
  const { page, limit, uploader, role_slug } = params;
  const offset = (page - 1) * limit;

  let resourcesList: Resource[];

  if (useResourceDemoData()) {
    resourcesList = demoRows
      .filter((item) => !item.deleted_at)
      .map((item) => buildResourceFromDemoRow(item));
  } else {
    const rows = await fetchResourcesFromDbRows(params);
    resourcesList = await hydrateDbResources(rows);
  }

  if (params.search) {
    const keyword = params.search.toLowerCase();
    resourcesList = resourcesList.filter((item) =>
      `${item.resource_name} ${item.resource_description ?? ""}`
        .toLowerCase()
        .includes(keyword),
    );
  }

  if (params.resource_type) {
    resourcesList = resourcesList.filter((item) => item.resource_type === params.resource_type);
  }

  if (uploader) {
    const keyword = uploader.toLowerCase();
    resourcesList = resourcesList.filter((item) => {
      const full = `${item.uploader.first_name} ${item.uploader.last_name}`.toLowerCase();
      return full.includes(keyword);
    });
  }

  if (role_slug) {
    const keyword = role_slug.toLowerCase();
    resourcesList = resourcesList.filter((item) =>
      item.audiences.some((audience) => audience.role?.slug.toLowerCase().includes(keyword)),
    );
  }

  const total = resourcesList.length;
  const items = resourcesList.slice(offset, offset + limit);

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

export async function queryResourceById(id: number) {
  if (useResourceDemoData()) {
    const row = demoRows.find((item) => item.id === id && !item.deleted_at) ?? null;
    if (!row) {
      return {
        msg: "Resource not found",
        data: null,
      };
    }

    return {
      msg: "Resource retrieved successfully",
      data: buildResourceFromDemoRow(row),
    };
  }

  const matched = await fetchResourceByIdFromDb(id);

  if (!matched) {
    return {
      msg: "Resource not found",
      data: null,
    };
  }

  const hydrated = await hydrateDbResources([matched]);
  return {
    msg: "Resource retrieved successfully",
    data: hydrated[0] ?? null,
  };
}

export async function createResource(payload: CreateResourceInput, uploader?: AuthUploader) {
  if (useResourceDemoData()) {
    const roleIds = normalizeRoleIds(payload.role_ids, FALLBACK_ROLES);
    const authUploader = FALLBACK_UPLOADERS[0];
    const id = nextDemoResourceId++;

    const row: DemoResourceRow = {
      id,
      uploader_user_id: authUploader.id,
      track_id: payload.track_id ?? null,
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

    demoRows = [row, ...demoRows];
    demoAudienceRows = [
      ...roleIds.map((roleId) => ({
        id: nextDemoAudienceId++,
        resource_id: id,
        role_id: roleId,
        track_id: row.track_id,
      })),
      ...demoAudienceRows,
    ];

    return {
      msg: "Resource created successfully",
      data: buildResourceFromDemoRow(row),
    };
  }

  const uploaderProfile = await resolveUploaderForDb(uploader);
  const availableRoles = await getRolesFromDb();
  const roleIds = normalizeRoleIds(payload.role_ids, availableRoles);
  const id = await nextResourceIdFromDb();
  const storageKey = buildStorageKey(id);

  await db.insert(resources).values({
    id,
    uploaderUserId: uploaderProfile.id,
    trackId: payload.track_id ?? null,
    visibilityScope: "role_based",
    uploadedAt: new Date().toISOString(),
    deletedAt: null,
  });
  dbResourceExtras.set(id, {
    resource_name: payload.resource_name,
    resource_description: payload.resource_description,
    resource_type: payload.resource_type ?? null,
    file_name: null,
    file_mime_type: null,
    file_size: null,
    storage_key: storageKey,
  });

  let nextAudienceId = await nextAudienceIdFromDb();
  if (roleIds.length) {
    await db.insert(resourceAudience).values(
      roleIds.map((roleId) => ({
        id: nextAudienceId++,
        resourceId: id,
        roleId,
        trackId: payload.track_id ?? null,
      })),
    );
  }

  return queryResourceById(id).then((result) => ({
    msg: "Resource created successfully",
    data: result.data,
  }));
}

export async function uploadResource(payload: {
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
  if (useResourceDemoData()) {
    const created = await createResource(
      {
        resource_name: payload.resource_name,
        resource_description: payload.resource_description,
        resource_type: payload.resource_type,
        track_id: payload.track_id,
        role_ids: payload.role_ids,
      },
      payload.uploader,
    );

    if (!created.data) {
      return {
        msg: "Resource upload failed",
        data: null,
      };
    }

    const updated = {
      ...created.data,
      file_name: payload.file_name,
      file_mime_type: payload.file_mime_type || "application/octet-stream",
      file_size: payload.file_size,
      storage_key: buildStorageKey(created.data.id, payload.file_name),
    };

    demoRows = demoRows.map((item) =>
      item.id === updated.id
        ? {
            ...item,
            file_name: updated.file_name,
            file_mime_type: updated.file_mime_type,
            file_size: updated.file_size,
            storage_key: updated.storage_key,
          }
        : item,
    );

    uploadedFiles.set(updated.storage_key, {
      file_name: payload.file_name,
      mime_type: payload.file_mime_type || "application/octet-stream",
      bytes: payload.file_bytes,
    });

    return {
      msg: "Resource uploaded successfully",
      data: buildResourceFromDemoRow(
        demoRows.find((item) => item.id === updated.id) as DemoResourceRow,
      ),
    };
  }

  const uploaderProfile = await resolveUploaderForDb(payload.uploader);
  const availableRoles = await getRolesFromDb();
  const roleIds = normalizeRoleIds(payload.role_ids, availableRoles);
  const id = await nextResourceIdFromDb();
  const storageKey = buildStorageKey(id, payload.file_name);

  await db.insert(resources).values({
    id,
    uploaderUserId: uploaderProfile.id,
    trackId: payload.track_id ?? null,
    visibilityScope: "role_based",
    uploadedAt: new Date().toISOString(),
    deletedAt: null,
  });
  dbResourceExtras.set(id, {
    resource_name: payload.resource_name,
    resource_description: payload.resource_description,
    resource_type: payload.resource_type ?? null,
    file_name: payload.file_name,
    file_mime_type: payload.file_mime_type || "application/octet-stream",
    file_size: payload.file_size,
    storage_key: storageKey,
  });

  let nextAudienceId = await nextAudienceIdFromDb();
  if (roleIds.length) {
    await db.insert(resourceAudience).values(
      roleIds.map((roleId) => ({
        id: nextAudienceId++,
        resourceId: id,
        roleId,
        trackId: payload.track_id ?? null,
      })),
    );
  }

  uploadedFiles.set(storageKey, {
    file_name: payload.file_name,
    mime_type: payload.file_mime_type || "application/octet-stream",
    bytes: payload.file_bytes,
  });

  return queryResourceById(id).then((result) => ({
    msg: "Resource uploaded successfully",
    data: result.data,
  }));
}

export async function downloadResource(id: number) {
  const resourceResult = await queryResourceById(id);
  if (!resourceResult.data) {
    return {
      msg: "Resource not found",
      data: null,
    } as const;
  }

  const file = uploadedFiles.get(resourceResult.data.storage_key);
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

export async function updateResource(id: number, updates: UpdateResourceInput) {
  if (useResourceDemoData()) {
    const index = demoRows.findIndex((item) => item.id === id && !item.deleted_at);
    if (index === -1) {
      return { msg: "Resource not found", data: null };
    }

    const current = demoRows[index];
    const updated: DemoResourceRow = {
      ...current,
      resource_name: updates.resource_name ?? current.resource_name,
      resource_description: updates.resource_description ?? current.resource_description,
      resource_type:
        updates.resource_type === undefined ? current.resource_type : updates.resource_type,
      track_id: updates.track_id === undefined ? current.track_id : updates.track_id,
    };
    demoRows[index] = updated;

    if (updates.role_ids) {
      const roleIds = normalizeRoleIds(updates.role_ids, FALLBACK_ROLES);
      demoAudienceRows = demoAudienceRows.filter((item) => item.resource_id !== id);
      demoAudienceRows.push(
        ...roleIds.map((roleId) => ({
          id: nextDemoAudienceId++,
          resource_id: id,
          role_id: roleId,
          track_id: updated.track_id,
        })),
      );
    }

    return {
      msg: "Resource updated successfully",
      data: buildResourceFromDemoRow(updated),
    };
  }

  const existing = await queryResourceById(id);
  if (!existing.data) {
    return { msg: "Resource not found", data: null };
  }

  const current = existing.data;
  await db
    .update(resources)
    .set({
      trackId: updates.track_id === undefined ? current.track_id : updates.track_id,
    })
    .where(eq(resources.id, id));

  dbResourceExtras.set(id, {
    resource_name: updates.resource_name ?? current.resource_name,
    resource_description: updates.resource_description ?? current.resource_description,
    resource_type:
      updates.resource_type === undefined ? current.resource_type : updates.resource_type,
    file_name: current.file_name,
    file_mime_type: current.file_mime_type,
    file_size: current.file_size,
    storage_key: current.storage_key,
  });

  if (updates.role_ids) {
    const availableRoles = await getRolesFromDb();
    const roleIds = normalizeRoleIds(updates.role_ids, availableRoles);
    await db.delete(resourceAudience).where(eq(resourceAudience.resourceId, id));

    let nextAudienceId = await nextAudienceIdFromDb();
    if (roleIds.length) {
      await db.insert(resourceAudience).values(
        roleIds.map((roleId) => ({
          id: nextAudienceId++,
          resourceId: id,
          roleId,
          trackId: updates.track_id === undefined ? current.track_id : updates.track_id,
        })),
      );
    }
  }

  return queryResourceById(id).then((result) => ({
    msg: "Resource updated successfully",
    data: result.data,
  }));
}

export async function deleteResource(id: number) {
  if (useResourceDemoData()) {
    const index = demoRows.findIndex((item) => item.id === id && !item.deleted_at);
    if (index === -1) {
      return { msg: "Resource not found", data: null };
    }

    demoRows[index] = {
      ...demoRows[index],
      deleted_at: new Date().toISOString(),
    };
    return { msg: "Resource deleted successfully", data: null };
  }

  const existing = await queryResourceById(id);
  if (!existing.data) {
    return { msg: "Resource not found", data: null };
  }

  await db
    .update(resources)
    .set({ deletedAt: new Date().toISOString() })
    .where(eq(resources.id, id));

  dbResourceExtras.delete(id);
  uploadedFiles.delete(existing.data.storage_key);

  return {
    msg: "Resource deleted successfully",
    data: null,
  };
}

export async function assignRoleToResource(id: number, roleId: number) {
  if (useResourceDemoData()) {
    const row = demoRows.find((item) => item.id === id && !item.deleted_at);
    if (!row) return { msg: "Resource not found", data: null };

    if (!FALLBACK_ROLES.some((item) => item.id === roleId)) {
      return { msg: "Role not found", data: null };
    }

    const exists = demoAudienceRows.some(
      (item) => item.resource_id === id && item.role_id === roleId,
    );
    if (!exists) {
      demoAudienceRows.push({
        id: nextDemoAudienceId++,
        resource_id: id,
        role_id: roleId,
        track_id: row.track_id,
      });
    }

    return {
      msg: "Role assigned successfully",
      data: buildResourceFromDemoRow(row),
    };
  }

  const roleRows = await getRolesFromDb();
  if (!roleRows.some((item) => item.id === roleId)) {
    return { msg: "Role not found", data: null };
  }

  const existing = await queryResourceById(id);
  if (!existing.data) {
    return { msg: "Resource not found", data: null };
  }

  const hasRole = existing.data.audiences.some((item) => item.role_id === roleId);
  if (!hasRole) {
    const nextId = await nextAudienceIdFromDb();
    await db.insert(resourceAudience).values({
      id: nextId,
      resourceId: id,
      roleId,
      trackId: existing.data.track_id,
    });
  }

  return queryResourceById(id).then((result) => ({
    msg: "Role assigned successfully",
    data: result.data,
  }));
}

export async function removeRoleFromResource(id: number, roleId: number) {
  const availableRoles = useResourceDemoData() ? FALLBACK_ROLES : await getRolesFromDb();
  const adminRole = availableRoles.find((item) => item.slug === ADMIN_ROLE_SLUG);

  if (adminRole && roleId === adminRole.id) {
    const current = await queryResourceById(id);
    return {
      msg: "Admin visibility is required and cannot be removed",
      data: current.data,
    };
  }

  if (useResourceDemoData()) {
    const row = demoRows.find((item) => item.id === id && !item.deleted_at);
    if (!row) return { msg: "Resource not found", data: null };

    demoAudienceRows = demoAudienceRows.filter(
      (item) => !(item.resource_id === id && item.role_id === roleId),
    );

    return {
      msg: "Role removed successfully",
      data: buildResourceFromDemoRow(row),
    };
  }

  const existing = await queryResourceById(id);
  if (!existing.data) {
    return { msg: "Resource not found", data: null };
  }

  await db
    .delete(resourceAudience)
    .where(and(eq(resourceAudience.resourceId, id), eq(resourceAudience.roleId, roleId)));

  return queryResourceById(id).then((result) => ({
    msg: "Role removed successfully",
    data: result.data,
  }));
}

export async function listResourceRoles() {
  if (useResourceDemoData()) {
    return {
      msg: "Roles retrieved successfully",
      data: FALLBACK_ROLES,
    };
  }

  const dbRoles = await getRolesFromDb();
  return {
    msg: "Roles retrieved successfully",
    data: dbRoles,
  };
}

export function listResourceTypes() {
  return {
    msg: "Resource types retrieved successfully",
    data: FALLBACK_TYPES,
  };
}
