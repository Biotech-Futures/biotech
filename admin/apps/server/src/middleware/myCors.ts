import { cors } from "hono/cors";

const myCors = cors({
  origin: ["http://localhost:3000"],
  allowHeaders: ["Content-Type", "Authorization", "x-timezone"],
  allowMethods: ["POST", "GET", "OPTIONS", "PUT", "DELETE", "PATCH"],
  exposeHeaders: ["Content-Length"],
  maxAge: 600,
  credentials: true,
});

export default myCors;
