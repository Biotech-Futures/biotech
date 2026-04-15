import { Hono } from "hono";
import { sValidator } from "@hono/standard-validator";
import { confirmMentorAssignmentSchema, replaceMentorSchema } from "./schema.js";
import {
  bulkReplaceInactiveMentors,
  confirmMentorAssignments,
  getMatchedGroups,
  getMentors,
  getUnmatchedGroups,
  matchMentor,
  replaceMentor,
} from "./service.js";

export const mentorMatchRoute = new Hono();

mentorMatchRoute.get("/recommend", async (c) => {
  const { id } = c.get("user");
  const rawMode = c.req.query("mode");
  const mode =
    rawMode === "strict" || rawMode === "coverage" ? rawMode : "balanced";
  const data = await matchMentor(id, mode);
  return c.json({ msg: "Mentor recommendations retrieved successfully", data });
});

mentorMatchRoute.get("/mentors", async (c) => {
  const data = await getMentors();
  return c.json({ msg: "Mentors retrieved successfully", data });
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
    return c.json({ msg: "Mentor assignments confirmed", data });
  },
);

mentorMatchRoute.get("/matched-groups", async (c) => {
  const data = await getMatchedGroups();
  return c.json({ msg: "Matched groups retrieved successfully", data });
});

mentorMatchRoute.post(
  "/replace",
  sValidator("json", replaceMentorSchema),
  async (c) => {
    const payload = c.req.valid("json");
    const data = await replaceMentor(payload);
    return c.json({ msg: "Mentor replaced successfully", data });
  },
);

mentorMatchRoute.post("/bulk-replace-inactive", async (c) => {
  const data = await bulkReplaceInactiveMentors();
  return c.json({ msg: "Inactive mentor assignments removed", data });
});
