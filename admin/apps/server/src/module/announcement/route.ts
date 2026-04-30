import { Hono } from "hono";
import { sValidator } from "@hono/standard-validator";
import {
  queryAnnouncementsSchema,
  createAnnouncementSchema,
  updateAnnouncementSchema,
} from "./schema.js";
import {
  listAnnouncements,
  getAnnouncementById,
  createAnnouncement,
  updateAnnouncement,
  archiveAnnouncement,
  sendAnnouncementEmail,
  listAnnouncementTracks,
  listAnnouncementRoles,
} from "./service.js";

export const announcementRoute = new Hono();

function parseId(value: string) {
  const n = Number.parseInt(value, 10);
  return Number.isNaN(n) ? null : n;
}

announcementRoute.get(
  "/",
  sValidator("query", queryAnnouncementsSchema),
  async (c) => {
    const params = c.req.valid("query");
    const result = await listAnnouncements(params);
    return c.json(result);
  },
);

announcementRoute.get("/tracks", async (c) => {
  return c.json(await listAnnouncementTracks());
});

announcementRoute.get("/roles", async (c) => {
  return c.json(await listAnnouncementRoles());
});

announcementRoute.get("/:id", async (c) => {
  const id = parseId(c.req.param("id"));
  if (!id) return c.json({ msg: "Invalid id", data: null }, 400);
  return c.json(await getAnnouncementById(id));
});

announcementRoute.post(
  "/",
  sValidator("json", createAnnouncementSchema),
  async (c) => {
    const input = c.req.valid("json");
    // TODO: replace with real admin user id from session when auth middleware is wired
    const authorUserId = 1;
    const result = await createAnnouncement(input, authorUserId);
    return c.json(result, 201);
  },
);

announcementRoute.put(
  "/:id",
  sValidator("json", updateAnnouncementSchema),
  async (c) => {
    const id = parseId(c.req.param("id"));
    if (!id) return c.json({ msg: "Invalid id", data: null }, 400);
    const input = c.req.valid("json");
    return c.json(await updateAnnouncement(id, input));
  },
);

announcementRoute.post("/:id/archive", async (c) => {
  const id = parseId(c.req.param("id"));
  if (!id) return c.json({ msg: "Invalid id", data: null }, 400);
  return c.json(await archiveAnnouncement(id));
});

announcementRoute.post("/:id/notify", async (c) => {
  const id = parseId(c.req.param("id"));
  if (!id) return c.json({ msg: "Invalid id", data: null }, 400);
  return c.json(await sendAnnouncementEmail(id));
});
