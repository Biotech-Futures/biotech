import db from "@/lib/db.js";
import {
  deleteBlobFile,
  downloadBlobFile,
  uploadBlobFile,
} from "@/lib/blob.js";
import {
  groups,
  resourceAudience,
  resourceTypes,
  resources,
  roles,
  tracks,
  users,
} from "@/schema/db.js";
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
  name?: string;
};

export type ResourceTypeName = "document" | "guide" | "video" | "template";
export type ResourceKind = "file" | "page";
export type VisibilityScope = "global" | "track_based" | "role_based";

export type ResourceTypeOption = {
  value: ResourceTypeName;
  label: string;
};

export type ResourceTrackOption = {
  id: number;
  code: string;
  label: string;
};

export type ResourceUploader = {
  id: string | number;
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
  uploader_user_id: string | number;
  track_id: number | null;
  visibility_scope: string;
  uploaded_at: string;
  deleted_at: string | null;
  resource_kind: ResourceKind;
  resource_name: string;
  resource_description: string | null;
  resource_type: ResourceTypeName | null;
  content_html: string | null;
  file_name: string | null;
  file_mime_type: string | null;
  file_size: number | null;
  storage_key: string | null;
  group_id: number | null;
  resource_type_id: number | null;
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
let demoUploadersState: ResourceUploader[] = FALLBACK_UPLOADERS.map((item) => ({ ...item }));
let nextDemoResourceId = Math.max(0, ...demoRows.map((item) => item.id)) + 1;
let nextDemoAudienceId = Math.max(0, ...demoAudienceRows.map((item) => item.id)) + 1;
let nextDemoUploaderId =
  Math.max(100, ...demoUploadersState.map((item) => Number(item.id) || 0)) + 1;

const demoUploadedFiles = new Map<
  string,
  {
    file_name: string;
    mime_type: string;
    bytes: ArrayBuffer;
  }
>();

function normalizeRoleIds(roleIds: number[] = [], availableRoles: Role[]): number[] {
  const adminRole = availableRoles.find((item) => item.slug === ADMIN_ROLE_SLUG);
  const validIds = roleIds.filter((roleId) => availableRoles.some((item) => item.id === roleId));
  const withAdmin = adminRole ? [...validIds, adminRole.id] : validIds;
  return Array.from(new Set(withAdmin));
}

function slugifyRole(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function resolveVisibilityScope(trackId: number | null | undefined, roleIds: number[] = []) {
  if (roleIds.length > 0) return "role_based" as const;
  if (trackId !== null && trackId !== undefined) return "track_based" as const;
  return "global" as const;
}

function normalizeVisibilityScope(
  value: string | null | undefined,
  trackId: number | null | undefined,
  roleIds: number[] = [],
) {
  if (value === "global" || value === "track_based" || value === "role_based") {
    return value;
  }
  return resolveVisibilityScope(trackId, roleIds);
}

function buildStorageKey(resourceId: number, fileName?: string | null) {
  const stamp = Date.now();
  const safeName = (fileName || "resource.bin").replace(/[^a-zA-Z0-9._-]/g, "_");
  return `resources/${stamp}-${resourceId}-${safeName}`;
}

function extractFileNameFromStorageKey(storageKey?: string | null) {
  if (!storageKey) return null;
  const parts = storageKey.split("/");
  const raw = parts[parts.length - 1] || "";
  const dashIndex = raw.indexOf("-", raw.indexOf("-") + 1);
  if (dashIndex === -1) return raw || null;
  return raw.slice(dashIndex + 1) || null;
}

function buildResourceFromDemoRow(resourceRow: DemoResourceRow): Resource {
  const uploader =
    demoUploadersState.find((item) => item.id === resourceRow.uploader_user_id) ??
    demoUploadersState[0] ??
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
    group_id: null,
    resource_type_id: null,
    uploader,
    audiences,
  };
}

async function getRolesFromDb(): Promise<Role[]> {
  const rows = await db
    .select({ id: roles.id, name: roles.roleName })
    .from(roles)
    .orderBy(asc(roles.id));

  if (!rows.length) return [];
  return rows.map((item) => ({
    id: item.id,
    name: item.name,
    slug: slugifyRole(item.name),
  }));
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
  if (authUploader?.id) {
    const userId = Number(authUploader.id);
    if (Number.isFinite(userId)) {
      const matched = await db
        .select({
          id: users.id,
          firstName: users.firstName,
          lastName: users.lastName,
          email: users.email,
        })
        .from(users)
        .where(eq(users.id, userId))
        .limit(1);

      if (matched[0]) {
        return {
          id: matched[0].id,
          first_name: matched[0].firstName,
          last_name: matched[0].lastName,
          email: matched[0].email,
        };
      }
    }
  }

  if (authUploader?.email) {
    const matched = await db
      .select({
        id: users.id,
        firstName: users.firstName,
        lastName: users.lastName,
        email: users.email,
      })
      .from(users)
      .where(eq(users.email, authUploader.email))
      .limit(1);

    if (matched[0]) {
      return {
        id: matched[0].id,
        first_name: matched[0].firstName,
        last_name: matched[0].lastName,
        email: matched[0].email,
      };
    }
  }

  const firstUser = await db
    .select({
      id: users.id,
      firstName: users.firstName,
      lastName: users.lastName,
      email: users.email,
    })
    .from(users)
    .orderBy(asc(users.id))
    .limit(1);

  if (firstUser[0]) {
    return {
      id: firstUser[0].id,
      first_name: firstUser[0].firstName,
      last_name: firstUser[0].lastName,
      email: firstUser[0].email,
    };
  }

  throw new Error("Cannot resolve uploader: missing user mapping in users table");
}

function resolveUploaderForDemo(authUploader?: AuthUploader): ResourceUploader {
  if (!authUploader) {
    return demoUploadersState[0] ?? FALLBACK_UPLOADERS[0];
  }

  if (authUploader.email) {
    const byEmail = demoUploadersState.find(
      (item) => item.email.toLowerCase() === authUploader.email?.toLowerCase(),
    );
    if (byEmail) return byEmail;
  }

  const parsed = parseName(authUploader.name);
  const created: ResourceUploader = {
    id: nextDemoUploaderId++,
    first_name: parsed.first,
    last_name: parsed.last,
    email: authUploader.email || `admin-${Date.now()}@example.com`,
  };
  demoUploadersState = [created, ...demoUploadersState];
  return created;
}

async function fetchResourcesFromDbRows(params: QueryResourcesInput) {
  const conditions = [isNull(resources.deletedAt)];

  const uploaderId =
    params.uploader_user_id !== undefined ? Number(params.uploader_user_id) : null;
  if (uploaderId !== null && Number.isFinite(uploaderId)) {
    conditions.push(eq(resources.uploadedById, uploaderId));
  }

  if (params.group_id !== undefined) {
    conditions.push(eq(resources.groupId, params.group_id));
  }

  if (params.resource_kind) {
    conditions.push(eq(resources.kind, params.resource_kind));
  }

  if (params.resource_type_id !== undefined) {
    conditions.push(eq(resources.typeId, params.resource_type_id));
  }

  if (params.resource_type) {
    conditions.push(eq(resourceTypes.name, params.resource_type));
  }

  if (params.track_id !== undefined) {
    conditions.push(sql`COALESCE(${resources.trackId}, ${groups.trackId}) = ${params.track_id}`);
  }

  if (params.search) {
    const pattern = `%${params.search}%`;
    conditions.push(
      sql`(${resources.name} ILIKE ${pattern} OR ${resources.description} ILIKE ${pattern})`,
    );
  }

  const rows = await db
    .select({
      id: resources.id,
      uploader_user_id: resources.uploadedById,
      group_id: resources.groupId,
      track_id: sql<number | null>`(COALESCE(${resources.trackId}, ${groups.trackId}))::int`,
      visibility_scope: resources.visibilityScope,
      uploaded_at: resources.uploadedAt,
      deleted_at: resources.deletedAt,
      resource_kind: sql<ResourceKind>`${resources.kind}`,
      resource_name: resources.name,
      resource_description: resources.description,
      resource_type_id: resources.typeId,
      resource_type: sql<ResourceTypeName | null>`${resourceTypes.name}`,
      content_html: sql<string | null>`null`,
      file_name: sql<string | null>`null`,
      file_mime_type: resources.fileMimeType,
      file_size: resources.fileSize,
      storage_key: resources.storageKey,
    })
    .from(resources)
    .leftJoin(groups, eq(resources.groupId, groups.id))
    .leftJoin(resourceTypes, eq(resources.typeId, resourceTypes.id))
    .where(and(...conditions))
    .orderBy(
      params.order === "oldest"
        ? asc(resources.uploadedAt)
        : desc(resources.uploadedAt),
    );

  return rows as ResourceRow[];
}

async function fetchResourceByIdFromDb(id: number): Promise<ResourceRow | null> {
  const row = await db
    .select({
      id: resources.id,
      uploader_user_id: resources.uploadedById,
      group_id: resources.groupId,
      track_id: sql<number | null>`(COALESCE(${resources.trackId}, ${groups.trackId}))::int`,
      visibility_scope: resources.visibilityScope,
      uploaded_at: resources.uploadedAt,
      deleted_at: resources.deletedAt,
      resource_kind: sql<ResourceKind>`${resources.kind}`,
      resource_name: resources.name,
      resource_description: resources.description,
      resource_type_id: resources.typeId,
      resource_type: sql<ResourceTypeName | null>`${resourceTypes.name}`,
      content_html: sql<string | null>`null`,
      file_name: sql<string | null>`null`,
      file_mime_type: resources.fileMimeType,
      file_size: resources.fileSize,
      storage_key: resources.storageKey,
    })
    .from(resources)
    .leftJoin(groups, eq(resources.groupId, groups.id))
    .leftJoin(resourceTypes, eq(resources.typeId, resourceTypes.id))
    .where(and(eq(resources.id, id), isNull(resources.deletedAt)))
    .limit(1);

  if (!row[0]) return null;
  return row[0] as ResourceRow;
}

async function hydrateDbResources(resourceRows: ResourceRow[]): Promise<Resource[]> {
  if (!resourceRows.length) return [];

  const uploaderIds = Array.from(
    new Set(resourceRows.map((item) => String(item.uploader_user_id))),
  );
  const uploaderRows = await db
    .select({
      id: users.id,
      firstName: users.firstName,
      lastName: users.lastName,
      email: users.email,
    })
    .from(users)
    .where(inArray(users.id, uploaderIds.map((value) => Number(value)).filter(Number.isFinite)));

  const uploaderMap = new Map(
    uploaderRows.map((item) => {
      return [
        item.id,
        {
          id: item.id,
          first_name: item.firstName,
          last_name: item.lastName,
          email: item.email,
        },
      ] as const;
    }),
  );
  const resourceIds = resourceRows.map((item) => item.id);

  const audienceRows = await db
    .select({
      id: resourceAudience.id,
      resource_id: resourceAudience.resourceId,
      role_id: resourceAudience.roleId,
      track_id: resourceAudience.trackId,
      role_name: roles.roleName,
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
      role:
        row.role_id && row.role_name
          ? { id: row.role_id, slug: slugifyRole(row.role_name) }
          : null,
      track_id: row.track_id,
    });
    audienceMap.set(row.resource_id, existing);
  }

  return resourceRows.map((row) => {
    const audiences = audienceMap.get(row.id) ?? [];
    const roleIds = audiences
      .map((item) => item.role_id)
      .filter((id): id is number => typeof id === "number");
    const visibility = normalizeVisibilityScope(row.visibility_scope, row.track_id, roleIds);

    return {
      ...row,
      visibility_scope: visibility,
      file_name: row.file_name ?? extractFileNameFromStorageKey(row.storage_key),
      uploader:
        uploaderMap.get(Number(row.uploader_user_id)) ?? {
          id: row.uploader_user_id,
          first_name: "Unknown",
          last_name: "User",
          email: "unknown@example.com",
        },
      audiences,
    };
  });
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

  if (params.uploader_user_id !== undefined) {
    resourcesList = resourcesList.filter(
      (item) => String(item.uploader_user_id) === String(params.uploader_user_id),
    );
  }

  if (params.track_id !== undefined) {
    resourcesList = resourcesList.filter(
      (item) => Number(item.track_id) === Number(params.track_id),
    );
  }

  if (params.resource_type) {
    resourcesList = resourcesList.filter((item) => item.resource_type === params.resource_type);
  }

  if (params.resource_kind) {
    resourcesList = resourcesList.filter((item) => item.resource_kind === params.resource_kind);
  }

  if (uploader) {
    const keyword = uploader.toLowerCase();
    resourcesList = resourcesList.filter((item) => {
      const full = `${item.uploader.first_name} ${item.uploader.last_name}`.toLowerCase();
      const email = item.uploader.email.toLowerCase();
      return full.includes(keyword) || email.includes(keyword);
    });
  }

  if (role_slug) {
    const keyword = role_slug.toLowerCase();
    resourcesList = resourcesList.filter((item) =>
      item.audiences.some((audience) => audience.role?.slug.toLowerCase().includes(keyword)),
    );
  }

  const getTimestamp = (resource: Resource) => {
    const parsed = Date.parse(resource.uploaded_at ?? "");
    if (!Number.isNaN(parsed)) return parsed;
    return 0;
  };

  resourcesList.sort((a, b) => {
    if (params.order === "oldest") {
      return (
        getTimestamp(a) - getTimestamp(b) ||
        a.resource_name.localeCompare(b.resource_name)
      );
    }

    return (
      getTimestamp(b) - getTimestamp(a) ||
      a.resource_name.localeCompare(b.resource_name)
    );
  });

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
  const resource = hydrated[0] ?? null;

  if (resource && resource.resource_kind === "page" && resource.storage_key) {
    const blobFile = await downloadBlobFile(resource.storage_key);
    if (blobFile?.bytes) {
      try {
        resource.content_html = new TextDecoder().decode(new Uint8Array(blobFile.bytes));
      } catch {
        // Ignore decode issues; content_html stays null.
      }
    }
  }

  return {
    msg: "Resource retrieved successfully",
    data: resource,
  };
}

export async function createResource(payload: CreateResourceInput, uploader?: AuthUploader) {
  if (useResourceDemoData()) {
    const requestedRoleIds = payload.role_ids ?? [];
    const visibilityScope: VisibilityScope =
      payload.visibility_scope ?? resolveVisibilityScope(payload.track_id, requestedRoleIds);
    const roleIds = normalizeRoleIds(requestedRoleIds, FALLBACK_ROLES);
    const trackId = payload.track_id ?? null;
    const authUploader = resolveUploaderForDemo(uploader);
    const id = nextDemoResourceId++;

    const row: DemoResourceRow = {
      id,
      uploader_user_id: Number(authUploader.id),
      track_id: trackId,
      visibility_scope: visibilityScope,
      uploaded_at: new Date().toISOString(),
      deleted_at: null,
      resource_kind: payload.resource_kind ?? "file",
      resource_name: payload.resource_name,
      resource_description: payload.resource_description,
      resource_type: payload.resource_type ?? "guide",
      content_html: payload.resource_kind === "page" ? (payload.content_html ?? "") : null,
      file_name: payload.resource_kind === "page" ? null : null,
      file_mime_type: payload.resource_kind === "page" ? null : null,
      file_size: payload.resource_kind === "page" ? null : null,
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
  const requestedRoleIds = payload.role_ids ?? [];
  const roleIds = normalizeRoleIds(requestedRoleIds, availableRoles);
  const requestedResourceType = payload.resource_type ?? null;

  const groupId = payload.group_id ?? null;

  const resourceTypeId =
    payload.resource_type_id ??
    (requestedResourceType
      ? await (async () => {
          const matched = await db
            .select({ id: resourceTypes.id })
            .from(resourceTypes)
            .where(eq(resourceTypes.name, requestedResourceType))
            .limit(1);
          return matched[0]?.id ?? null;
        })()
      : null);

  const [inserted] = await db
    .insert(resources)
    .values({
      name: payload.resource_name,
      description: payload.resource_description,
      kind: payload.resource_kind ?? "file",
      uploadedAt: sql`statement_timestamp()`,
      deletedAt: null,
      uploadedById: Number(uploaderProfile.id),
      typeId: resourceTypeId,
      fileMimeType: null,
      fileSize: null,
      visibilityScope:
        payload.visibility_scope ??
        resolveVisibilityScope(payload.track_id, requestedRoleIds),
      trackId: payload.track_id ?? null,
      groupId,
      storageKey: null,
    })
    .returning({ id: resources.id });

  const id = inserted?.id;
  if (!id) {
    throw new Error("Failed to create resource");
  }

  if ((payload.resource_kind ?? "file") === "page") {
    const htmlText = payload.content_html ?? "";
    const fileName = `${payload.resource_name || "resource"}.html`;
    const storageKey = buildStorageKey(id, fileName);
    const bytes = new TextEncoder().encode(htmlText).buffer;

    if (useResourceDemoData()) {
      demoUploadedFiles.set(storageKey, {
        file_name: fileName,
        mime_type: "text/html",
        bytes,
      });
    } else {
      await uploadBlobFile(storageKey, bytes, "text/html");
    }

    await db
      .update(resources)
      .set({
        storageKey,
        fileMimeType: "text/html",
        fileSize: bytes.byteLength,
      })
      .where(eq(resources.id, id));
  }

  if (roleIds.length) {
    await db
      .insert(resourceAudience)
      .values(roleIds.map((roleId) => ({ resourceId: id, roleId, trackId: payload.track_id ?? null })));
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
  resource_type_id?: number;
  visibility_scope?: VisibilityScope;
  track_id?: number;
  group_id?: number;
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
        visibility_scope:
          payload.visibility_scope ??
          resolveVisibilityScope(payload.track_id, payload.role_ids ?? []),
        resource_kind: "file",
        content_html: null,
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

    demoUploadedFiles.set(updated.storage_key, {
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
  const requestedRoleIds = payload.role_ids ?? [];
  const roleIds = normalizeRoleIds(requestedRoleIds, availableRoles);
  const requestedResourceType = payload.resource_type ?? null;

  const groupId = payload.group_id ?? null;

  const resourceTypeId =
    payload.resource_type_id ??
    (requestedResourceType
      ? await (async () => {
          const matched = await db
            .select({ id: resourceTypes.id })
            .from(resourceTypes)
            .where(eq(resourceTypes.name, requestedResourceType))
            .limit(1);
          return matched[0]?.id ?? null;
        })()
      : null);

  const fileMimeType = payload.file_mime_type || "application/octet-stream";

  const [inserted] = await db
    .insert(resources)
    .values({
      name: payload.resource_name,
      description: payload.resource_description,
      kind: "file",
      uploadedAt: sql`statement_timestamp()`,
      deletedAt: null,
      uploadedById: Number(uploaderProfile.id),
      typeId: resourceTypeId,
      fileMimeType,
      fileSize: payload.file_size,
      visibilityScope:
        payload.visibility_scope ??
        resolveVisibilityScope(payload.track_id, requestedRoleIds),
      trackId: payload.track_id ?? null,
      groupId,
      storageKey: null,
    })
    .returning({ id: resources.id });

  const id = inserted?.id;
  if (!id) {
    throw new Error("Failed to upload resource");
  }

  const storageKey = buildStorageKey(id, payload.file_name);

  await uploadBlobFile(storageKey, payload.file_bytes, fileMimeType);

  await db
    .update(resources)
    .set({ storageKey })
    .where(eq(resources.id, id));

  if (roleIds.length) {
    await db
      .insert(resourceAudience)
      .values(roleIds.map((roleId) => ({ resourceId: id, roleId, trackId: payload.track_id ?? null })));
  }

  return queryResourceById(id).then((result) => ({
    msg: "Resource uploaded successfully",
    data: result.data,
  }));
}

export async function replaceResourceFile(
  id: number,
  payload: {
    file_name: string;
    file_size: number;
    file_mime_type?: string;
    file_bytes: ArrayBuffer;
  },
) {
  const existing = await queryResourceById(id);
  if (!existing.data) {
    return {
      msg: "Resource not found",
      data: null,
    };
  }

  if (existing.data.resource_kind === "page") {
    return {
      msg: "HTML page resource cannot replace file",
      data: null,
    };
  }

  const nextStorageKey = buildStorageKey(id, payload.file_name);

  if (useResourceDemoData()) {
    const index = demoRows.findIndex((item) => item.id === id && !item.deleted_at);
    if (index === -1) {
      return { msg: "Resource not found", data: null };
    }

    const previousKey = demoRows[index].storage_key;
    demoRows[index] = {
      ...demoRows[index],
      file_name: payload.file_name,
      file_mime_type: payload.file_mime_type || "application/octet-stream",
      file_size: payload.file_size,
      storage_key: nextStorageKey,
    };

    if (previousKey && previousKey !== nextStorageKey) {
      demoUploadedFiles.delete(previousKey);
    }
    demoUploadedFiles.set(nextStorageKey, {
      file_name: payload.file_name,
      mime_type: payload.file_mime_type || "application/octet-stream",
      bytes: payload.file_bytes,
    });

    return {
      msg: "Resource file replaced successfully",
      data: buildResourceFromDemoRow(demoRows[index]),
    };
  }

  await uploadBlobFile(
    nextStorageKey,
    payload.file_bytes,
    payload.file_mime_type || "application/octet-stream",
  );

  await db
    .update(resources)
    .set({
      fileMimeType: payload.file_mime_type || "application/octet-stream",
      fileSize: payload.file_size,
      storageKey: nextStorageKey,
    })
    .where(eq(resources.id, id));

  if (existing.data.storage_key && existing.data.storage_key !== nextStorageKey) {
    await deleteBlobFile(existing.data.storage_key);
  }

  return queryResourceById(id).then((result) => ({
    msg: "Resource file replaced successfully",
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

  if (resourceResult.data.resource_kind === "page") {
    return {
      msg: "This resource is an HTML page and cannot be downloaded as a file",
      data: null,
    } as const;
  }

  if (useResourceDemoData()) {
    if (!resourceResult.data.storage_key) {
      return {
        msg: "This resource has no uploaded file",
        data: null,
      } as const;
    }

    const file = demoUploadedFiles.get(resourceResult.data.storage_key);
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

  if (!resourceResult.data.storage_key) {
    return {
      msg: "This resource has no uploaded file",
      data: null,
    } as const;
  }

  const blobFile = await downloadBlobFile(resourceResult.data.storage_key);
  if (!blobFile) {
    return {
      msg: "File not found in storage",
      data: null,
    } as const;
  }

  return {
    msg: "Resource download prepared",
    data: {
      file_name: resourceResult.data.file_name || `resource-${resourceResult.data.id}`,
      mime_type: blobFile.mime_type,
      bytes: blobFile.bytes,
    },
  } as const;
}

export async function updateResource(id: number, updates: UpdateResourceInput) {
  if (useResourceDemoData()) {
    const index = demoRows.findIndex((item) => item.id === id && !item.deleted_at);
    if (index === -1) {
      return { msg: "Resource not found", data: null };
    }

    const current = demoRows[index];
    const adminRoleId = FALLBACK_ROLES.find((role) => role.slug === ADMIN_ROLE_SLUG)?.id;
    const currentNonAdminRoleIds = demoAudienceRows
      .filter((item) => item.resource_id === id && item.role_id !== null)
      .map((item) => item.role_id as number)
      .filter((roleId) => roleId !== adminRoleId);
    const requestedRoleIds =
      updates.role_ids === undefined ? currentNonAdminRoleIds : updates.role_ids;
    const nextTrackId = updates.track_id === undefined ? current.track_id : updates.track_id;
    const visibilityScope: VisibilityScope =
      updates.visibility_scope ??
      (current.visibility_scope as VisibilityScope) ??
      resolveVisibilityScope(nextTrackId, requestedRoleIds);

    const updated: DemoResourceRow = {
      ...current,
      resource_kind: updates.resource_kind ?? current.resource_kind,
      resource_name: updates.resource_name ?? current.resource_name,
      resource_description: updates.resource_description ?? current.resource_description,
      resource_type:
        updates.resource_type === undefined ? current.resource_type : updates.resource_type,
      content_html:
        updates.content_html === undefined ? current.content_html : updates.content_html,
      visibility_scope: visibilityScope,
      track_id: nextTrackId,
    };
    if (updated.resource_kind === "page") {
      updated.file_name = null;
      updated.file_mime_type = null;
      updated.file_size = null;
    }
    demoRows[index] = updated;

    if (updates.role_ids !== undefined) {
      const roleIds = normalizeRoleIds(requestedRoleIds, FALLBACK_ROLES);
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
  const updateKind = updates.resource_kind ?? current.resource_kind;
  const requestedResourceType = updates.resource_type ?? null;

  const nextGroupId =
    updates.group_id === undefined
      ? current.group_id
      : updates.group_id === null
        ? null
        : updates.group_id;

  const finalGroupId = nextGroupId;

  const nextResourceTypeId =
    updates.resource_type_id === undefined
      ? current.resource_type_id
      : updates.resource_type_id === null
        ? null
        : updates.resource_type_id;

  const typeIdFromName =
    requestedResourceType !== null
      ? await (async () => {
          const matched = await db
            .select({ id: resourceTypes.id })
            .from(resourceTypes)
            .where(eq(resourceTypes.name, requestedResourceType))
            .limit(1);
          return matched[0]?.id ?? null;
        })()
      : null;

  const finalResourceTypeId = typeIdFromName ?? nextResourceTypeId;

  await db
    .update(resources)
    .set({
      name: updates.resource_name ?? current.resource_name,
      description: updates.resource_description ?? current.resource_description ?? "",
      typeId: finalResourceTypeId,
      kind: updateKind,
      visibilityScope: updates.visibility_scope ?? current.visibility_scope,
      trackId: updates.track_id === undefined ? current.track_id : updates.track_id,
      groupId: finalGroupId,
    })
    .where(eq(resources.id, id));

  // For page resources, keep HTML content in blob storage.
  if (updateKind === "page" && updates.content_html !== undefined) {
    const htmlText = updates.content_html ?? "";
    const fileName = `${(updates.resource_name ?? current.resource_name) || "resource"}.html`;
    const storageKey = buildStorageKey(id, fileName);
    const bytes = new TextEncoder().encode(htmlText).buffer;

    await uploadBlobFile(storageKey, bytes, "text/html");

    if (current.storage_key && current.storage_key !== storageKey) {
      await deleteBlobFile(current.storage_key);
    }

    await db
      .update(resources)
      .set({
        storageKey,
        fileMimeType: "text/html",
        fileSize: bytes.byteLength,
      })
      .where(eq(resources.id, id));
  }

  if (updates.role_ids !== undefined) {
    const availableRoles = await getRolesFromDb();
    const currentNonAdminRoleIds = current.audiences
      .filter((item) => item.role_id !== null && item.role?.slug !== ADMIN_ROLE_SLUG)
      .map((item) => item.role_id as number);
    const requestedRoleIds = updates.role_ids ?? currentNonAdminRoleIds;
    const roleIds = normalizeRoleIds(requestedRoleIds, availableRoles);

    await db.delete(resourceAudience).where(eq(resourceAudience.resourceId, id));
    if (roleIds.length) {
      await db.insert(resourceAudience).values(
        roleIds.map((roleId) => ({
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

  if (useResourceDemoData()) {
    if (existing.data.storage_key) {
      demoUploadedFiles.delete(existing.data.storage_key);
    }
  } else {
    if (existing.data.storage_key) {
      await deleteBlobFile(existing.data.storage_key);
    }
  }

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
    await db.insert(resourceAudience).values({
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

export async function listResourceTypes() {
  if (useResourceDemoData()) {
    return {
      msg: "Resource types retrieved successfully",
      data: FALLBACK_TYPES,
    };
  }

  const rows = await db
    .select({
      id: resourceTypes.id,
      name: resourceTypes.name,
    })
    .from(resourceTypes)
    .orderBy(asc(resourceTypes.name));

  if (!rows.length) {
    return {
      msg: "Resource types retrieved successfully",
      data: [],
    };
  }

  return {
    msg: "Resource types retrieved successfully",
    data: rows.map((row) => ({
      id: row.id,
      value: row.name as ResourceTypeName,
      label: row.name,
    })),
  };
}

export async function listResourceTracks() {
  const rows = await db
    .select({
      id: tracks.id,
      code: tracks.trackName,
    })
    .from(tracks)
    .orderBy(asc(tracks.trackName));

  return {
    msg: "Tracks retrieved successfully",
    data: rows.map((row) => ({
      id: row.id,
      code: row.code,
      label: row.code,
    })),
  };
}
