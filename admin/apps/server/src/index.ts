import { serve } from "@hono/node-server";
import { Hono } from "hono";
import myCors from "./middleware/myCors.js";
import { logger } from "hono/logger";
import { matchRoute } from "./module/match/route.js";
import { groupRoute } from "./module/group/route.js";
import { demoRoute } from "./module/demo/route.js";
import { mentorMatchRoute } from "./module/mentorMatch/route.js";
import { resourceRoute } from "./module/resource/route.js";
import { userRoute } from "./module/user/route.js";

const app = new Hono();

app.get("/", (c) => {
  return c.text("Hello Hono!");
});
app.use(logger());
app.use("*", myCors);

app
  .basePath("/api/v1")
  .route("match", matchRoute)
  .route("group", groupRoute)
  .route("demo", demoRoute)
  .route("mentor-match", mentorMatchRoute)
  .route("resource", resourceRoute)
  .route("user", userRoute);

serve(
  {
    fetch: app.fetch,
    port: 3003,
  },
  (info) => {
    console.log(`Server is running on http://localhost:${info.port}`);
  },
);
