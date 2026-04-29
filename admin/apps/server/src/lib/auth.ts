import { betterAuth } from "better-auth";
import { drizzleAdapter } from "better-auth/adapters/drizzle";
import db from "./db.js";
import { magicLink } from "better-auth/plugins";
import { sendEmail } from "./email.js";
import { admin } from "better-auth/plugins";
import {
  adminAccount,
  adminSession,
  adminUser,
  adminVerification,
} from "@/schema/admin.js";

export const auth = betterAuth({
  user: {
    additionalFields: {
      userId: {
        type: "number",
        required: true,
        fieldName: "userid",
      },
      tracks: {
        type: "json",
        required: false,
        fieldName: "tracks",
      },
    },
  },
  database: drizzleAdapter(db, {
    provider: "pg",
    schema: {
      user: adminUser,
      account: adminAccount,
      session: adminSession,
      verification: adminVerification,
    },
  }),
  plugins: [
    admin(),
    magicLink({
      disableSignUp: true,
      sendMagicLink: async ({ email, token, url, metadata }, ctx) => {
        const html = `
          <div style="background:#f4f7fb;padding:32px 16px;font-family:Inter,Segoe UI,Helvetica,Arial,sans-serif;color:#0f172a;">
            <div style="max-width:560px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;border-radius:14px;padding:28px;box-shadow:0 12px 30px rgba(15,23,42,0.08);">
              <h1 style="margin:0 0 12px;font-size:24px;line-height:1.3;color:#0f172a;">Sign in to Biotech Admin</h1>
              <p style="margin:0 0 20px;font-size:14px;line-height:1.7;color:#334155;">
                Click the secure magic link below to continue. This link is one-time use and will expire soon.
              </p>
              <a href="${url}" style="display:inline-block;background:#0f766e;color:#ffffff;text-decoration:none;font-weight:600;font-size:14px;padding:12px 18px;border-radius:10px;">
                Sign In Securely
              </a>
              <p style="margin:20px 0 8px;font-size:12px;color:#64748b;">If the button does not work, use this link:</p>
              <p style="margin:0;word-break:break-all;">
                <a href="${url}" style="font-size:12px;color:#0f766e;text-decoration:underline;">${url}</a>
              </p>
            </div>
          </div>
        `;

        await sendEmail({
          to: email,
          subject: "Your Magic Link",
          text: `Click the link to sign in: ${url}`,
          html,
        });
      },
    }),
  ],
  trustedOrigins: ["http://localhost:3000", "http://localhost:3003"],
});
