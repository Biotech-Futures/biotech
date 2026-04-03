import { Hono } from "hono";
import { sValidator } from "@hono/standard-validator";
import { confirmMentorAssignmentSchema } from "./schema.js";
import {
  confirmMentorAssignments,
  getUnmatchedGroups,
  matchMentor,
} from "./service.js";

export const mentorMatchRoute = new Hono();

mentorMatchRoute.get("/recommend", async (c) => {
  const data = await matchMentor();
  return c.json({ msg: "Mentor recommendations retrieved successfully", data });
});

mentorMatchRoute.get("/groups", async (c) => {
  const data = await getUnmatchedGroups();
  return c.json({ msg: "Unmatched groups retrieved successfully", data });
});

mentorMatchRoute.post(
  "/confirm",
  sValidator("json", confirmMentorAssignmentSchema),
  async (c) => {
    const payload = c.req.valid("json");
    const data = await confirmMentorAssignments(payload);
    return c.json({
      msg: "Mentor assignments confirmed",
      data,
    });
  },
);
