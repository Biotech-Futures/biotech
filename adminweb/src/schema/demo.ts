import { z } from "zod";
export const createDemoSchema = z.object({
  name: z.string().min(2).max(100),
  age: z.number().min(0).max(150),
});

export type CreateDemo = z.infer<typeof createDemoSchema>;
