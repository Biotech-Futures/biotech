import { Hono } from "hono";
import { getIndividualStudents, matchStudent } from "./service.js";

export const matchRoute = new Hono();

matchRoute.get("/student", async (c) => {
  const data = await matchStudent();
  return c.json({ data });
});

matchRoute.get("/individual", async (c) => {
  const data = await getIndividualStudents();
  return c.json({ data });
});
