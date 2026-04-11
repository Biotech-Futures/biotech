import "dotenv/config";
import { defineConfig } from "drizzle-kit";
export default defineConfig({
  out: "./drizzle",
  schema: ["./src/db/schema"],
  dialect: "postgresql",
  schemaFilter: ["admin_user", "public"],

  dbCredentials: {
    url: process.env.DATABASE_URL!,
  },
});
