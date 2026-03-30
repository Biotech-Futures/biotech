import { serve } from "@hono/node-server";
import { Hono } from "hono";
import myCors from "./middleware/myCors.js";
import { logger } from "hono/logger";
import { matchRoute } from "./module/match/route.js";

const app = new Hono();

app.get("/", (c) => {
  return c.text("Hello Hono!");
});
app.use(logger());
app.use("*", myCors);

app.basePath("/api/v1").route("match", matchRoute);

serve(
  {
    fetch: app.fetch,
    port: 3001,
  },
  (info) => {
    console.log(`Server is running on http://localhost:${info.port}`);
  },
);
