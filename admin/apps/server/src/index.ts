import { serve } from "@hono/node-server";
import { Hono } from "hono";
import myCors from "./middleware/myCors.js";
import { logger } from "hono/logger";
import { matchRoute } from "./module/match/route.js";
import { groupRoute } from "./module/group/route.js";
import { demoRoute } from "./module/demo/route.js";
import { mentorMatchRoute } from "./module/mentorMatch/route.js";
import { userRoute } from "./module/user/route.js";
import { auth } from "./lib/auth.js";
import { HTTPException } from "hono/http-exception";

const app = new Hono();

app.get("/", (c) => {
  return c.text("Hello Hono!");
});
app.use(logger());
app.use("*", myCors);

app.on(["POST", "GET"], "/api/auth/*", (c) => {
  return auth.handler(c.req.raw);
});

app
  .basePath("/api/v1")
  .route("match", matchRoute)
  .route("group", groupRoute)
  .route("demo", demoRoute)
  .route("mentor-match", mentorMatchRoute)
  .route("user", userRoute);

app.onError((error, c) => {
  console.log("Error occurred:", error);
  if (error instanceof HTTPException) {
    return c.json(
      { error: true, message: error.message, code: error.status },
      error.status,
    );
  }

  return c.json({ error: true, message: error.message, code: 500 }, 500);
});
serve(
  {
    fetch: app.fetch,
    port: 3003,
  },
  (info) => {
    console.log(`Server is running on http://localhost:${info.port}`);
  },
);
