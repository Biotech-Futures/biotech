import { createFileRoute, Outlet, useMatchRoute } from "@tanstack/react-router";
import { PageHeader } from "@/components/layout/PageHeader";
import type { PageTab } from "@/components/layout/PageTabs";

const GRADING_TABS: PageTab[] = [
  { label: "Mark by Component", to: "/grading/by-component" },
  { label: "Mark by Group", to: "/grading/by-group" },
];

export const Route = createFileRoute("/_auth/grading")({
  component: GradingLayout,
});

function GradingLayout() {
  const matchRoute = useMatchRoute();
  const onHub =
    matchRoute({ to: "/grading/by-component", fuzzy: false }) ||
    matchRoute({ to: "/grading/by-group", fuzzy: false });

  return (
    <div className="p-4 space-y-4">
      <PageHeader title="Grading" tabs={onHub ? GRADING_TABS : undefined} />
      <Outlet />
    </div>
  );
}
