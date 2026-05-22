import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { AlertCircleIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export const Route = createFileRoute("/auth/callback")({
  component: RouteComponent,
});

const ERROR_MESSAGES: Record<string, { title: string; description: string }> = {
  invalid_or_expired_code: {
    title: "Link expired",
    description:
      "This login link has already been used or has expired. Please request a new one.",
  },
  too_many_attempts: {
    title: "Too many attempts",
    description:
      "Too many failed login attempts. Please wait a few minutes and try again.",
  },
  account_inactive: {
    title: "Account inactive",
    description:
      "Your account has been suspended or deactivated. Please contact an administrator.",
  },
};

function RouteComponent() {
  const navigate = useNavigate();
  const search = new URLSearchParams(window.location.search);
  const success = search.get("success") === "true";
  const error = search.get("error") ?? null;

  useEffect(() => {
    if (success) {
      window.location.href = "/";
    }
  }, [success]);

  if (success) return null;

  const errorInfo = (error ? ERROR_MESSAGES[error] : undefined) ?? {
    title: "Something went wrong",
    description: "An unexpected error occurred. Please try again.",
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-muted/40">
      <Card className="w-full max-w-md">
        <CardContent className="flex flex-col items-center gap-4 py-10 text-center">
          <AlertCircleIcon className="size-12 text-destructive" />
          <div className="space-y-1">
            <h1 className="text-xl font-semibold">{errorInfo.title}</h1>
            <p className="text-sm text-muted-foreground">
              {errorInfo.description}
            </p>
          </div>
          <Button variant="outline" onClick={() => navigate({ to: "/signin" })}>
            Back to sign in
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
