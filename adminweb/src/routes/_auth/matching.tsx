import { createFileRoute, redirect } from "@tanstack/react-router";

// Merged into the Groups & Matching hub (Student Matching tab). Kept as a
// redirect so /matching?run=true still auto-runs the matcher.
export const Route = createFileRoute("/_auth/matching")({
  beforeLoad: ({ location }) => {
    throw redirect({
      to: "/groups/student-matching",
      search: location.search as never,
    });
  },
});
