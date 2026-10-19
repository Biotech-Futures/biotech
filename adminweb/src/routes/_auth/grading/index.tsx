import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/_auth/grading/")({
  beforeLoad: () => {
    throw redirect({ to: "/grading/by-component" });
  },
});
