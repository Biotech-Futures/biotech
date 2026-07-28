import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { AlertCircleIcon, MailCheckIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useVerifyLoginCode } from "@/fetch/auth";
import { SUPPORT_EMAIL } from "@/lib/brand";

export const Route = createFileRoute("/auth/callback")({
  component: RouteComponent,
});

const ERROR_MESSAGES: Record<
  string,
  { title: string; description: React.ReactNode }
> = {
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
    description: (
      <>
        Your account has been suspended or deactivated. Please contact an
        administrator at{" "}
        <a
          href={`mailto:${SUPPORT_EMAIL}`}
          className="font-medium underline underline-offset-4"
        >
          {SUPPORT_EMAIL}
        </a>
        .
      </>
    ),
  },
};

function RouteComponent() {
  const navigate = useNavigate();
  const search = new URLSearchParams(window.location.search);
  const success = search.get("success") === "true";
  const email = search.get("email");
  const code = search.get("code");
  const [confirmError, setConfirmError] = useState("");
  const verifyLoginCode = useVerifyLoginCode();
  const error = search.get("error") ?? null;

  useEffect(() => {
    // Legacy shape: the backend used to open the session before redirecting.
    if (success) {
      window.location.href = "/";
    }
  }, [success]);

  if (success) return null;

  // Mail scanners fetch the link but never press a button, so gating the code
  // behind an explicit click is what stops them consuming it.
  if (email && code && !error) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-muted/40">
        <Card className="w-full max-w-md">
          <CardContent className="flex flex-col items-center gap-4 py-10 text-center">
            <MailCheckIcon className="size-12 text-primary" />
            <div className="space-y-1">
              <h1 className="text-xl font-semibold">Confirm sign-in</h1>
              <p className="text-sm text-muted-foreground">
                Press continue to finish signing in as{" "}
                <span className="font-medium text-foreground">{email}</span>.
              </p>
            </div>
            <Button
              className="w-full"
              loading={verifyLoginCode.isPending}
              onClick={() => {
                setConfirmError("");
                verifyLoginCode.mutate(
                  { email, code },
                  {
                    onSuccess: () => window.location.assign("/"),
                    onError: () =>
                      setConfirmError(
                        "This login link has already been used or has expired. Please request a new one.",
                      ),
                  },
                );
              }}
            >
              Continue to sign in
            </Button>
            {confirmError && (
              <p className="text-sm text-destructive" role="alert">
                {confirmError}
              </p>
            )}
            <Button variant="ghost" onClick={() => navigate({ to: "/signin" })}>
              Back to sign in
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

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
