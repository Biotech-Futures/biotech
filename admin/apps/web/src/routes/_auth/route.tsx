import Layout from "@/components/layout";
import { useAuth } from "@/lib/mock-auth";
import { createFileRoute, Outlet, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";

export const Route = createFileRoute("/_auth")({
  component: RouteComponent,
});

function RouteComponent() {
  const { isAuthenticated, isHydrated } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (isHydrated && !isAuthenticated) {
      void navigate({ to: "/login" });
    }
  }, [isAuthenticated, isHydrated, navigate]);

  if (!isHydrated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background text-sm text-muted-foreground">
        Restoring session...
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return (
    <Layout>
      <Outlet />
    </Layout>
  );
}
