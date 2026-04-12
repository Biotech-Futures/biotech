import { auth } from "@/lib/auth.js";
import { createMiddleware } from "hono/factory";
import { HTTPException } from "hono/http-exception";

export const authRequirement = createMiddleware(async (c, next) => {
  const session = await auth.api.getSession({ headers: c.req.raw.headers });
  if (!session) {
    throw new HTTPException(401, { message: "Unauthorized" });
  }
  const { user, session: sessionData } = session;
  c.set("user", user);
  c.set("session", sessionData);
  await next();
});
