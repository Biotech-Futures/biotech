import { Hono } from "hono";

export const groupRoute = new Hono();

groupRoute.get("/", (c) => {
  return c.json({ message: "Group route" });
});
