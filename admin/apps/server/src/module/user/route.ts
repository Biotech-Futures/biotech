import { Hono } from "hono";
import { sValidator } from "@hono/standard-validator";
import {
  queryUsersSchema,
  queryStudentsSchema,
  createUserSchema,
  bulkCreateUsersSchema,
  updateUserSchema,
} from "./schema.js";
import {
  queryUsers,
  queryStudents,
  queryUserById,
  createUser,
  bulkCreateUsers,
  updateUser,
  deleteUser,
} from "./service.js";

export const userRoute = new Hono();

// GET /api/v1/user - List users with pagination and filters
userRoute.get("/", sValidator("query", queryUsersSchema), (c) => {
  const params = c.req.valid("query");
  const result = queryUsers(params);
  return c.json(result);
});

// GET /api/v1/user/students - List students with student-specific filters
userRoute.get("/students", sValidator("query", queryStudentsSchema), (c) => {
  const params = c.req.valid("query");
  const result = queryStudents(params);
  return c.json(result);
});

// GET /api/v1/user/:id - Get single user
userRoute.get("/:id", (c) => {
  const id = c.req.param("id");
  const result = queryUserById(id);
  return c.json(result);
});

// POST /api/v1/user - Create single user
userRoute.post("/", sValidator("json", createUserSchema), (c) => {
  const data = c.req.valid("json");
  const result = createUser(data);
  return c.json(result);
});

// POST /api/v1/user/bulk - Bulk create users from CSV
userRoute.post("/bulk", sValidator("json", bulkCreateUsersSchema), (c) => {
  const data = c.req.valid("json");
  const result = bulkCreateUsers(data);
  return c.json(result);
});

// PUT /api/v1/user/:id - Update user
userRoute.put("/:id", sValidator("json", updateUserSchema), (c) => {
  const id = c.req.param("id");
  const data = c.req.valid("json");
  const result = updateUser(id, data);
  return c.json(result);
});

// DELETE /api/v1/user/:id - Delete user
userRoute.delete("/:id", (c) => {
  const id = c.req.param("id");
  const result = deleteUser(id);
  return c.json(result);
});
