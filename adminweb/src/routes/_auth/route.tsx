import Layout from "@/components/layout";
import { createFileRoute, Outlet, redirect } from "@tanstack/react-router";
import { myFetch } from "@/lib/myFetch";
import { isProductBuild } from "@/lib/authConfig";

export const Route = createFileRoute("/_auth")({
  beforeLoad: async ({ context, location }) => {
    if (!context.auth.isAuthenticated) {
      throw redirect({
        to: "/signin",
        search: {
          redirect: location.href,
        },
      });
    }

    // On first visit per session, check if admin needs to set a password.
    if (!isProductBuild && !sessionStorage.getItem("pwChecked")) {
      try {
        const res = await myFetch.get<{
          data: { hasPassword: boolean };
        }>("/auth/password-status/");
        if (res.data?.data?.hasPassword === false) {
          throw redirect({ to: "/setup-password" });
        }
      } catch (e) {
        // Re-throw redirects; silently ignore other errors (network, non-admin user).
        if (
          e != null &&
          typeof e === "object" &&
          "href" in (e as object)
        ) {
          throw e;
        }
      }
      sessionStorage.setItem("pwChecked", "1");
    }
  },
  component: RouteComponent,
});

function RouteComponent() {
  return (
    <Layout>
      <Outlet />
    </Layout>
  );
}
