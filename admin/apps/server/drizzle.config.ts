import "dotenv/config";
import { defineConfig } from "drizzle-kit";
export default defineConfig({
  out: "./src/drizzle",
  schema: "./src/drizzle/schema.ts",
  dialect: "postgresql",
  schemaFilter: ["public"],

  dbCredentials: {
    url: process.env.DATABASE_URL!,
  },
});
