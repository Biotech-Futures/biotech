import { Hono } from "hono";
import { sValidator } from "@hono/standard-validator";
import {
  createResourceSchema,
  queryResourcesSchema,
  updateResourceSchema,
} from "./schema.js";
import {
  createResource,
  deleteResource,
  queryResourceById,
  queryResourceRoles,
  queryResources,
  queryResourceTypes,
  updateResource,
} from "./service.js";

export const resourceRoute = new Hono();

resourceRoute.get("/", sValidator("query", queryResourcesSchema), (c) => {
  const params = c.req.valid("query");
  return c.json(queryResources(params));
});

resourceRoute.get("/roles", (c) => {
  return c.json(queryResourceRoles());
});

resourceRoute.get("/types", (c) => {
  return c.json(queryResourceTypes());
});

resourceRoute.get("/:id", (c) => {
  return c.json(queryResourceById(c.req.param("id")));
});

resourceRoute.post("/", sValidator("json", createResourceSchema), (c) => {
  const payload = c.req.valid("json");
  return c.json(createResource(payload));
});

resourceRoute.put("/:id", sValidator("json", updateResourceSchema), (c) => {
  const payload = c.req.valid("json");
  return c.json(updateResource(c.req.param("id"), payload));
});

resourceRoute.delete("/:id", (c) => {
  return c.json(deleteResource(c.req.param("id")));
});
