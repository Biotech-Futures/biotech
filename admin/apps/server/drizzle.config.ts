import "dotenv/config";
import { defineConfig } from "drizzle-kit";
export default defineConfig({
  out: "./src/new/drizzle",
  schema: "./src/schema/index.ts",
  dialect: "postgresql",
  schemaFilter: ["public", "admin"],

  dbCredentials: {
    url: process.env.DATABASE_URL!,
  },
});
