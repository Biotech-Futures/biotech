import Layout from "@/components/layout";
import { createFileRoute, Outlet, redirect } from "@tanstack/react-router";

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

    // On first visit per session, send anyone without a password to set one.
    //
    // This used to ask /api/v1/admin/auth/password-status/, which is behind
    // IsAdminScoped. A support agent — an account this app now creates, and
    // which is deliberately not an administrator — got a 403, the catch below
    // swallowed it as "network error", and they were never prompted. Following
    // the link themselves did not help either: the page posted to the matching
    // admin-scoped endpoint and answered "Please try again", which was never
    // going to be true.
    //
    // The answer was already in hand. AuthProvider has fetched /users/me/
    // before this router renders, and that payload carries the same fact for
    // every role. So this asks nobody: no request, no 403, nothing to swallow.
    //
    // `=== true` on purpose: if the field ever stops being sent, that is not a
    // reason to push every signed-in user into a password form.
    if (!sessionStorage.getItem("pwChecked")) {
      if (context.auth.user?.must_change_password === true) {
        throw redirect({ to: "/setup-password" });
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
