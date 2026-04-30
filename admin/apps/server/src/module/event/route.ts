import { Hono } from "hono";
import { sValidator } from "@hono/standard-validator";
import {
  createEventRsvpSchema,
  createEventSchema,
  queryEventsSchema,
  updateEventRsvpSchema,
  updateEventSchema,
} from "./schema.js";
import {
  createEventRsvp,
  queryEvents,
  queryEventById,
  queryEventTargets,
  createEvent,
  updateEvent,
  deleteEvent,
  queryEventRsvps,
  updateEventRsvp,
  queryGroups,
  queryRoles,
  queryTracks,
} from "./service.js";

export const eventRoute = new Hono();

eventRoute.get("/", sValidator("query", queryEventsSchema), async (c) => {
  const params = c.req.valid("query");
  const res = await queryEvents(params);
  return c.json(res);
});

eventRoute.put(
  "/rsvp/:rsvpId",
  sValidator("json", updateEventRsvpSchema),
  async (c) => {
    const rsvpId = c.req.param("rsvpId");
    const data = c.req.valid("json");
    const res = await updateEventRsvp(rsvpId, data);
    return c.json(res);
  },
);

eventRoute.get("/:id", async (c) => {
  const id = c.req.param("id");
  const res = await queryEventById(id);
  return c.json(res);
});

eventRoute.post("/", sValidator("json", createEventSchema), async (c) => {
  const data = c.req.valid("json");
  const res = await createEvent(data);
  return c.json(res);
});

eventRoute.put("/:id", sValidator("json", updateEventSchema), async (c) => {
  const id = c.req.param("id");
  const data = c.req.valid("json");
  const res = await updateEvent(id, data);
  return c.json(res);
});

eventRoute.delete("/:id", async (c) => {
  const id = c.req.param("id");
  const res = await deleteEvent(id);
  return c.json(res);
});

eventRoute.get("/:id/rsvp", async (c) => {
  const id = c.req.param("id");
  const res = await queryEventRsvps(id);
  return c.json(res);
});

eventRoute.post(
  "/:id/rsvp",
  sValidator("json", createEventRsvpSchema),
  async (c) => {
    const id = c.req.param("id");
    const data = c.req.valid("json");
    const res = await createEventRsvp(id, data);
    return c.json(res);
  },
);

eventRoute.get("/:id/targets", async (c) => {
  const id = c.req.param("id");
  const res = await queryEventTargets(id);
  return c.json(res);
});

eventRoute.get("/meta/groups", async (c) => {
  const res = await queryGroups();
  return c.json(res);
});

eventRoute.get("/meta/roles", async (c) => {
  const res = await queryRoles();
  return c.json(res);
});

eventRoute.get("/meta/tracks", async (c) => {
  const res = await queryTracks();
  return c.json(res);
});
