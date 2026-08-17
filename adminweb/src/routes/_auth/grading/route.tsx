import { createFileRoute, Outlet } from "@tanstack/react-router";
import { PageHeader } from "@/components/layout/PageHeader";

export const Route = createFileRoute("/_auth/grading")({
  component: GradingLayout,
});

function GradingLayout() {
  return (
    <div className="p-4 space-y-4">
      <PageHeader title="Grading" />
      <Outlet />
    </div>
  );
}
