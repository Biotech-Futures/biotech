import { createFileRoute, redirect } from "@tanstack/react-router";

// Merged into the Groups & Matching hub (Mentor Matching tab). Kept as a
// redirect for old links.
export const Route = createFileRoute("/_auth/mentorMatching")({
  beforeLoad: ({ location }) => {
    throw redirect({
      to: "/groups/mentor-matching",
      search: location.search as never,
    });
  },
});
