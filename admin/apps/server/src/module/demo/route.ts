import { Hono } from "hono";
import { sValidator } from "@hono/standard-validator";
import { createDemoSchema } from "./schema.js";
import { createDemo, queryDemo } from "./service.js";

export const demoRoute = new Hono();

demoRoute.get("/", (c) => {
  const data = queryDemo();
  return c.json(data);
});

demoRoute.post("/", sValidator("json", createDemoSchema), (c) => {
  const data = c.req.valid("json");
  const res = createDemo(data);
  return c.json(res);
});
