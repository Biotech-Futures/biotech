import { Hono } from "hono";
import { sValidator } from "@hono/standard-validator";
import {
  queryResourcesSchema,
  createResourceSchema,
  updateResourceSchema,
  updateResourceRoleSchema,
} from "./schema.js";
import {
  queryResources,
  queryResourceById,
  createResource,
  uploadResource,
  downloadResource,
  updateResource,
  replaceResourceFile,
  deleteResource,
  assignRoleToResource,
  removeRoleFromResource,
  listResourceRoles,
  listResourceTypes,
  listResourceTracks,
} from "./service.js";
import type { AuthUploader } from "./service.js";

export const resourceRoute = new Hono();

function parseId(value: string) {
  const parsed = Number.parseInt(value, 10);
  return Number.isNaN(parsed) ? null : parsed;
}

resourceRoute.get("/", sValidator("query", queryResourcesSchema), async (c) => {
  const params = c.req.valid("query");
  const result = await queryResources(params);
  return c.json(result);
});

resourceRoute.get("/roles", async (c) => {
  const result = await listResourceRoles();
  return c.json(result);
});

resourceRoute.get("/types", async (c) => {
  const result = await listResourceTypes();
  return c.json(result);
});

resourceRoute.get("/tracks", async (c) => {
  const result = await listResourceTracks();
  return c.json(result);
});

resourceRoute.get("/:id/download", async (c) => {
  const id = parseId(c.req.param("id"));
  if (id === null) {
    return c.json({ msg: "Invalid resource id", data: null }, 400);
  }

  const result = await downloadResource(id);

  if (!result.data) {
    return c.json(result, 404);
  }

  return new Response(result.data.bytes, {
    headers: {
      "Content-Type": result.data.mime_type || "application/octet-stream",
      "Content-Disposition": `attachment; filename="${encodeURIComponent(result.data.file_name)}"`,
    },
  });
});

resourceRoute.get("/:id", async (c) => {
  const id = parseId(c.req.param("id"));
  if (id === null) {
    return c.json({ msg: "Invalid resource id", data: null }, 400);
  }

  const result = await queryResourceById(id);
  return c.json(result);
});

resourceRoute.post("/", sValidator("json", createResourceSchema), async (c) => {
  const payload = c.req.valid("json");
  const user = c.get("user") as AuthUploader | undefined;
  const result = await createResource(payload, user);
  return c.json(result);
});

resourceRoute.post("/upload", async (c) => {
  const body = await c.req.parseBody({ all: true });

  const fileField = body.file;
  const file = Array.isArray(fileField) ? fileField[0] : fileField;
  if (!(file instanceof File)) {
    return c.json({ msg: "Please select a file to upload", data: null }, 400);
  }

  const getValue = (value: unknown) => (Array.isArray(value) ? value[0] : value);
  const resourceName = String(getValue(body.resource_name) ?? file.name).trim();
  const resourceDescription = String(getValue(body.resource_description) ?? "").trim();
  const resourceTypeRaw = getValue(body.resource_type);
  const resourceType = resourceTypeRaw ? String(resourceTypeRaw) : undefined;
  const visibilityScopeRaw = getValue(body.visibility_scope);
  const visibilityScope = visibilityScopeRaw
    ? String(visibilityScopeRaw)
    : undefined;
  const trackIdRaw = getValue(body.track_id);
  const trackId =
    trackIdRaw !== undefined && trackIdRaw !== null && String(trackIdRaw).trim() !== ""
      ? Number(trackIdRaw)
      : undefined;
  const groupIdRaw = getValue(body.group_id);
  const groupId =
    groupIdRaw !== undefined && groupIdRaw !== null && String(groupIdRaw).trim() !== ""
      ? Number(groupIdRaw)
      : undefined;
  const resourceTypeIdRaw = getValue(body.resource_type_id);
  const resourceTypeId =
    resourceTypeIdRaw !== undefined &&
    resourceTypeIdRaw !== null &&
    String(resourceTypeIdRaw).trim() !== ""
      ? Number(resourceTypeIdRaw)
      : undefined;

  const roleField = body.role_ids;
  const roleIds = Array.isArray(roleField)
    ? roleField.map((item) => Number(item)).filter((item) => Number.isFinite(item))
    : roleField
      ? [Number(roleField)].filter((item) => Number.isFinite(item))
      : undefined;

  if (!resourceName) {
    return c.json({ msg: "resource_name is required", data: null }, 400);
  }
  if (!resourceDescription) {
    return c.json({ msg: "resource_description is required", data: null }, 400);
  }

  const result = await uploadResource({
    resource_name: resourceName,
    resource_description: resourceDescription,
    resource_type: resourceType as
      | "document"
      | "guide"
      | "video"
      | "template"
      | undefined,
    visibility_scope: visibilityScope as "global" | "track_based" | "role_based" | undefined,
    track_id: Number.isFinite(trackId) ? trackId : undefined,
    group_id: Number.isFinite(groupId) ? groupId : undefined,
    resource_type_id: Number.isFinite(resourceTypeId) ? resourceTypeId : undefined,
    role_ids: roleIds,
    file_name: file.name,
    file_size: file.size,
    file_mime_type: file.type,
    file_bytes: await file.arrayBuffer(),
    uploader: c.get("user") as AuthUploader | undefined,
  });

  return c.json(result);
});

resourceRoute.post("/:id/upload", async (c) => {
  const id = parseId(c.req.param("id"));
  if (id === null) {
    return c.json({ msg: "Invalid resource id", data: null }, 400);
  }

  const body = await c.req.parseBody({ all: true });
  const fileField = body.file;
  const file = Array.isArray(fileField) ? fileField[0] : fileField;
  if (!(file instanceof File)) {
    return c.json({ msg: "Please select a file to upload", data: null }, 400);
  }

  const result = await replaceResourceFile(id, {
    file_name: file.name,
    file_size: file.size,
    file_mime_type: file.type,
    file_bytes: await file.arrayBuffer(),
  });

  if (!result.data) {
    return c.json(result, 404);
  }
  return c.json(result);
});

resourceRoute.patch("/:id", sValidator("json", updateResourceSchema), async (c) => {
  const id = parseId(c.req.param("id"));
  if (id === null) {
    return c.json({ msg: "Invalid resource id", data: null }, 400);
  }

  const updates = c.req.valid("json");
  const result = await updateResource(id, updates);
  return c.json(result);
});

resourceRoute.put("/:id", sValidator("json", updateResourceSchema), async (c) => {
  const id = parseId(c.req.param("id"));
  if (id === null) {
    return c.json({ msg: "Invalid resource id", data: null }, 400);
  }

  const updates = c.req.valid("json");
  const result = await updateResource(id, updates);
  return c.json(result);
});

resourceRoute.delete("/:id", async (c) => {
  const id = parseId(c.req.param("id"));
  if (id === null) {
    return c.json({ msg: "Invalid resource id", data: null }, 400);
  }

  const result = await deleteResource(id);
  return c.json(result);
});

resourceRoute.post("/:id/assign-role", sValidator("json", updateResourceRoleSchema), async (c) => {
  const id = parseId(c.req.param("id"));
  if (id === null) {
    return c.json({ msg: "Invalid resource id", data: null }, 400);
  }

  const payload = c.req.valid("json");
  const result = await assignRoleToResource(id, payload.role_id);
  return c.json(result);
});

resourceRoute.delete("/:id/remove-role", sValidator("json", updateResourceRoleSchema), async (c) => {
  const id = parseId(c.req.param("id"));
  if (id === null) {
    return c.json({ msg: "Invalid resource id", data: null }, 400);
  }

  const payload = c.req.valid("json");
  const result = await removeRoleFromResource(id, payload.role_id);
  return c.json(result);
});
