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
  updateResource,
  deleteResource,
  assignRoleToResource,
  removeRoleFromResource,
  listResourceRoles,
  listResourceTypes,
} from "./service.js";

export const resourceRoute = new Hono();

resourceRoute.get("/", sValidator("query", queryResourcesSchema), (c) => {
  const params = c.req.valid("query");
  const result = queryResources(params);
  return c.json(result);
});

resourceRoute.get("/roles", (c) => {
  const result = listResourceRoles();
  return c.json(result);
});

resourceRoute.get("/types", (c) => {
  const result = listResourceTypes();
  return c.json(result);
});

resourceRoute.get("/:id", (c) => {
  const id = c.req.param("id");
  const result = queryResourceById(id);
  return c.json(result);
});

resourceRoute.post("/", sValidator("json", createResourceSchema), (c) => {
  const payload = c.req.valid("json");
  const result = createResource(payload);
  return c.json(result);
});

resourceRoute.patch("/:id", sValidator("json", updateResourceSchema), (c) => {
  const id = c.req.param("id");
  const updates = c.req.valid("json");
  const result = updateResource(id, updates);
  return c.json(result);
});

resourceRoute.put("/:id", sValidator("json", updateResourceSchema), (c) => {
  const id = c.req.param("id");
  const updates = c.req.valid("json");
  const result = updateResource(id, updates);
  return c.json(result);
});

resourceRoute.delete("/:id", (c) => {
  const id = c.req.param("id");
  const result = deleteResource(id);
  return c.json(result);
});

resourceRoute.post("/:id/assign-role", sValidator("json", updateResourceRoleSchema), (c) => {
  const id = c.req.param("id");
  const payload = c.req.valid("json");
  const result = assignRoleToResource(id, payload.role_id);
  return c.json(result);
});

resourceRoute.delete("/:id/remove-role", sValidator("json", updateResourceRoleSchema), (c) => {
  const id = c.req.param("id");
  const payload = c.req.valid("json");
  const result = removeRoleFromResource(id, payload.role_id);
  return c.json(result);
});
