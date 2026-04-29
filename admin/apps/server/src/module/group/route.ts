import { Hono } from "hono";
import { sValidator } from "@hono/standard-validator";
import {
  queryGroupMessagesSchema,
  queryGroupsSchema,
  removeGroupMessageSchema,
  removeGroupMemberSchema,
  updateGroupSchema,
} from "./schema.js";
import {
  queryGroupMessages,
  queryGroups,
  queryGroupById,
  removeGroupMessage,
  removeGroupMember,
  updateGroup,
} from "./service.js";

export const groupRoute = new Hono();

// GET /api/v1/group - List groups with pagination and filters
groupRoute.get("/", sValidator("query", queryGroupsSchema), async (c) => {
  const params = c.req.valid("query");
  const result = await queryGroups(params);
  return c.json(result);
});

// GET /api/v1/group/:id/messages - View group message history
groupRoute.get(
  "/:id/messages",
  sValidator("query", queryGroupMessagesSchema),
  async (c) => {
    const id = c.req.param("id");
    const params = c.req.valid("query");
    const result = await queryGroupMessages(id, params);
    return c.json(result);
  },
);

// DELETE /api/v1/group/:id/messages/:messageId - Remove a message from a group
groupRoute.delete(
  "/:id/messages/:messageId",
  sValidator("param", removeGroupMessageSchema),
  async (c) => {
    const params = c.req.valid("param");
    const result = await removeGroupMessage(params);
    return c.json(result);
  },
);

// GET /api/v1/group/:id - Get single group
groupRoute.get("/:id", async (c) => {
  const id = c.req.param("id");
  const result = await queryGroupById(id);
  return c.json(result);
});

// PUT /api/v1/group/:id - Update group
groupRoute.put("/:id", sValidator("json", updateGroupSchema), async (c) => {
  const id = c.req.param("id");
  const updates = c.req.valid("json");
  const result = await updateGroup(id, updates);
  return c.json(result);
});

// DELETE /api/v1/group/:id/members/:userId - Remove a student from a group
groupRoute.delete(
  "/:id/members/:userId",
  sValidator("param", removeGroupMemberSchema),
  async (c) => {
    const id = c.req.param("id");
    const params = c.req.valid("param");
    const result = await removeGroupMember(id, params);
    return c.json(result);
  },
);
