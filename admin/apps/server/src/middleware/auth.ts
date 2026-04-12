import { auth } from "@/lib/auth.js";
import { createMiddleware } from "hono/factory";
import { HTTPException } from "hono/http-exception";

export const authRequirement = createMiddleware(async (c, next) => {
  const session = await auth.api.getSession({ headers: c.req.raw.headers });
  const user = session?.user ?? null;
  const sessionData = session?.session ?? null;
  c.set("user", user);
  c.set("session", sessionData);
  if (!user) {
    throw new HTTPException(401, { message: "Unauthorized" });
  }
  await next();
});
