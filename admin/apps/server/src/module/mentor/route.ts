import { Hono } from "hono";
import { getMentorList, setMentorActive } from "./service.js";

export const mentorRoute = new Hono();

mentorRoute.get("/", async (c) => {
  const data = await getMentorList();
  return c.json({ msg: "Mentor list retrieved successfully", data });
});

mentorRoute.patch("/:mentorId/active", async (c) => {
  const mentorId = Number(c.req.param("mentorId"));
  const body = await c.req.json<{ isActive: boolean }>();
  const data = await setMentorActive(mentorId, body.isActive);
  return c.json({ msg: "Mentor status updated", data });
});
