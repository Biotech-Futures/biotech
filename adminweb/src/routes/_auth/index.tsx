import { createFileRoute } from "@tanstack/react-router";
import { AdminHomePage } from "@/components/home/AdminHomePage";

// Nothing but the Route may be exported from a route file: an extra export
// turns off autoCodeSplitting for it, which cost 170 kB on the main chunk
// when the page component itself was exported from here for its test. The
// component lives in components/home/ and the test imports it from there.
export const Route = createFileRoute("/_auth/")({
  component: AdminHomePage,
});
