import { Hono } from "hono";
import { sValidator } from "@hono/standard-validator";
import {
  queryUsersSchema,
  queryStudentsSchema,
  createUserSchema,
  bulkCreateUsersSchema,
  updateUserSchema,
  updateStatusSchema,
} from "./schema.js";
import {
  queryUsers,
  queryUserById,
  createUser,
  bulkCreateUsers,
  queryTracks,
  updateUser,
  updateStatus,
  deleteUser,
} from "./service.js";

export const userRoute = new Hono();

// GET /api/v1/user - List users with pagination and filters
userRoute.get("/", sValidator("query", queryUsersSchema), async (c) => {
  const params = c.req.valid("query");
  const result = await queryUsers(params);
  return c.json(result);
});

// GET /api/v1/user/tracks - List tracks available for filtering and assignment
userRoute.get("/tracks", async (c) => {
  const result = await queryTracks();
  return c.json(result);
});

// GET /api/v1/user/:id - Get single user
userRoute.get("/:id", async (c) => {
  const id = c.req.param("id");
  const result = await queryUserById(id);
  return c.json(result);
});

// POST /api/v1/user - Create single user
userRoute.post("/", sValidator("json", createUserSchema), async (c) => {
  const data = c.req.valid("json");
  const result = await createUser(data);
  return c.json(result);
});

// POST /api/v1/user/bulk - Bulk create users (JSON array)
userRoute.post(
  "/bulk",
  sValidator("json", bulkCreateUsersSchema),
  async (c) => {
    const data = c.req.valid("json");
    const admin = c.get("user") as { id: string };
    const result = await bulkCreateUsers(data, admin.id);
    return c.json(result);
  },
);

// POST /api/v1/user/bulk-csv - Bulk create users from CSV text
// Expected CSV format (with header): firstName,lastName,email,role,track
userRoute.post("/bulk-csv", async (c) => {
  const admin = c.get("user") as { id: string };
  const csvText: string = await c.req.text();

  const lines = csvText
    .trim()
    .split("\n")
    .map((l: string) => l.trim())
    .filter(Boolean);
  if (lines.length < 2) {
    return c.json({
      msg: "CSV must have a header row and at least one data row",
      data: null,
    });
  }

  // Skip header row, parse data rows
  const dataLines = lines.slice(1);
  const parsed: Array<{
    firstName: string;
    lastName: string;
    email: string;
    role: string;
    track: string;
  }> = [];
  const parseErrors: string[] = [];

  for (const line of dataLines) {
    const cols = line.split(",").map((col: string) => col.trim());
    if (cols.length < 5) {
      parseErrors.push(`Invalid row (need 5 columns): "${line}"`);
      continue;
    }
    const [firstName, lastName, email, role, track] = cols;
    parsed.push({ firstName, lastName, email, role, track });
  }

  if (parsed.length === 0) {
    return c.json({ msg: "No valid rows found in CSV", data: { parseErrors } });
  }

  // Reuse bulk service (Zod will catch invalid role/track values per row)
  const result = await bulkCreateUsers({ users: parsed as any }, admin.id);
  return c.json({ ...result, data: { ...result.data, parseErrors } });
});

// PUT /api/v1/user/:id - Update user info or role
userRoute.put("/:id", sValidator("json", updateUserSchema), async (c) => {
  const id = c.req.param("id");
  const data = c.req.valid("json");
  const result = await updateUser(id, data);
  return c.json(result);
});

// PATCH /api/v1/user/:id/status - Activate or deactivate account
userRoute.patch(
  "/:id/status",
  sValidator("json", updateStatusSchema),
  async (c) => {
    const id = c.req.param("id");
    const data = c.req.valid("json");
    const result = await updateStatus(id, data);
    return c.json(result);
  },
);

// DELETE /api/v1/user/:id - Delete user
userRoute.delete("/:id", async (c) => {
  const id = c.req.param("id");
  const result = await deleteUser(id);
  return c.json(result);
});
