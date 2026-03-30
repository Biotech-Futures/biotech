import z from "zod";

export const createDemoSchema = z.object({
  name: z.string(),
  age: z.number(),
});
