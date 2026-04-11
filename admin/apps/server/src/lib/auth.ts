import { betterAuth } from "better-auth";
import { drizzleAdapter } from "better-auth/adapters/drizzle";
import db from "./db.js";
import { account, session, user, verification } from "@/db/schema/admin.js";
import { magicLink } from "better-auth/plugins";

export const auth = betterAuth({
  database: drizzleAdapter(db, {
    provider: "pg",
    schema: {
      user: user,
      account: account,
      session: session,
      verification: verification,
    },
  }),
  plugins: [
    magicLink({
      disableSignUp: true,
      sendMagicLink: async ({ email, token, url, metadata }, ctx) => {},
    }),
  ],
});
