import { LoginForm } from "@/components/login-form";
import { Card, CardContent } from "@/components/ui/card";
import { PRODUCT_LOGIN_URL, isProductBuild } from "@/lib/authConfig";
import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/signin")({
  beforeLoad: () => {
    if (isProductBuild) {
      throw redirect({ href: PRODUCT_LOGIN_URL });
    }
  },
  component: RouteComponent,
});

function RouteComponent() {
  return (
    <div className="flex items-center justify-center flex-1">
      <Card>
        <CardContent>
          <LoginForm />
        </CardContent>
      </Card>
    </div>
  );
}
