import "dotenv/config";
import { defineConfig } from "drizzle-kit";

export default defineConfig({
  out: "./src/new/drizzle",
  schema: "./src/schema/index.ts",
  dialect: "postgresql",
  // Team-owned schema only. Safe to use with `drizzle-kit push`.
  schemaFilter: ["admin"],
  dbCredentials: {
    url: process.env.DATABASE_URL!,
  },
});
