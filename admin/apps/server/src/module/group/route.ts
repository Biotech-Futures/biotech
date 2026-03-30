import { Hono } from "hono";
import { sValidator } from "@hono/standard-validator";
import { queryGroupsSchema, updateGroupSchema } from "./schema.js";
import { queryGroups, queryGroupById, updateGroup } from "./service.js";

export const groupRoute = new Hono();

// GET /api/v1/group - List groups with pagination and filters
groupRoute.get("/", sValidator("query", queryGroupsSchema), (c) => {
  const params = c.req.valid("query");
  const result = queryGroups(params);
  return c.json(result);
});

// GET /api/v1/group/:id - Get single group
groupRoute.get("/:id", (c) => {
  const id = c.req.param("id");
  const result = queryGroupById(id);
  return c.json(result);
});

// PUT /api/v1/group/:id - Update group
groupRoute.put("/:id", sValidator("json", updateGroupSchema), (c) => {
  const id = c.req.param("id");
  const updates = c.req.valid("json");
  const result = updateGroup(id, updates);
  return c.json(result);
});