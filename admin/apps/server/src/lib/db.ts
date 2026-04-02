import "dotenv/config";
import { drizzle } from "drizzle-orm/node-postgres";

function resolveSsl() {
  const sslFlag = process.env.DATABASE_SSL?.toLowerCase();
  const sslMode = process.env.PGSSLMODE?.toLowerCase();
  const connectionString = process.env.DATABASE_URL ?? "";

  if (sslFlag === "false" || sslMode === "disable") {
    return false;
  }

  if (
    sslFlag === "true" ||
    sslMode === "require" ||
    connectionString.includes("sslmode=require")
  ) {
    return { rejectUnauthorized: false };
  }

  return false;
}

const db = drizzle({
  connection: {
    connectionString: process.env.DATABASE_URL!,
    ssl: resolveSsl(),
  },
});

export default db;
