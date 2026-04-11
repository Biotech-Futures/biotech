import { Hono } from "hono";
import { sValidator } from "@hono/standard-validator";
import { confirmMatchAssignmentSchema, matchUidQuerySchema } from "./schema.js";
import {
  confirmStudentAssignments,
  getIndividualStudents,
  matchStudent,
} from "./service.js";

export const matchRoute = new Hono();

matchRoute.get(
  "/student",
  sValidator("query", matchUidQuerySchema),
  async (c) => {
    const { uid } = c.req.valid("query");
    const data = await matchStudent(uid);
    return c.json({ data });
  },
);

matchRoute.get("/individual", async (c) => {
  const data = await getIndividualStudents();
  return c.json({ data });
});

matchRoute.post(
  "/confirm",
  sValidator("json", confirmMatchAssignmentSchema),
  async (c) => {
    const payload = c.req.valid("json");
    const data = await confirmStudentAssignments(payload);
    return c.json({
      msg: "Student assignments confirmed",
      data,
    });
  },
);
