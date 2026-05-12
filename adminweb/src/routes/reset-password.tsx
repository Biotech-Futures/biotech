import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useRequestPasswordReset, useConfirmPasswordReset } from "@/fetch/auth";
import { resetCsrfToken } from "@/util/csrf";
import { AxiosError } from "axios";
import { CheckCircle, ArrowLeft, Eye, EyeOff } from "lucide-react";

export const Route = createFileRoute("/reset-password")({
  validateSearch: (search: Record<string, unknown>) => ({
    token: search.token as string | undefined,
  }),
  component: ResetPasswordPage,
});

function extractCode(error: unknown): string | null {
  if (error instanceof AxiosError) {
    const data = error.response?.data as Record<string, unknown> | undefined;
    if (data && typeof data.code === "string") return data.code;
  }
  return null;
}

function extractDetail(error: unknown, fallback: string): string {
  if (error instanceof AxiosError) {
    const data = error.response?.data as
      | { detail?: string; error?: string; message?: string }
      | undefined;
    return data?.detail || data?.error || data?.message || fallback;
  }
  if (error instanceof Error) return error.message;
  return fallback;
}

function extractFieldErrors(error: unknown): string[] {
  if (error instanceof AxiosError) {
    const data = error.response?.data as
      | { fields?: Record<string, string[]> }
      | undefined;
    if (data?.fields) return Object.values(data.fields).flat();
  }
  return [];
}

function ResetPasswordPage() {
  const { token } = Route.useSearch();
  const hasToken = Boolean(token);
  const navigate = useNavigate();
  const redirectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Request mode state
  const [email, setEmail] = useState("");
  const [requestError, setRequestError] = useState("");
  const [requestSuccess, setRequestSuccess] = useState(false);

  // Confirm mode state
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [passwordError, setPasswordError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<string[]>([]);
  const [resetComplete, setResetComplete] = useState(false);

  const requestReset = useRequestPasswordReset();
  const confirmReset = useConfirmPasswordReset();

  function validateEmail(value: string) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
  }

  function clearConfirmErrors() {
    setPasswordError("");
    setFieldErrors([]);
  }

  async function handleRequestReset() {
    setRequestError("");
    const normalizedEmail = email.trim().toLowerCase();

    if (!normalizedEmail) {
      setRequestError("Please enter your email address.");
      return;
    }
    if (!validateEmail(normalizedEmail)) {
      setRequestError("Please enter a valid email address.");
      return;
    }

    requestReset.mutate(normalizedEmail, {
      onSuccess: () => {
        setRequestSuccess(true);
      },
      onError: (error) => {
        const code = extractCode(error);
        if (
          code === "password_reset_rate_limited" ||
          code === "PasswordResetRateLimited"
        ) {
          setRequestError(
            "Too many password reset attempts. Please wait a while before trying again.",
          );
        } else {
          setRequestError(
            extractDetail(
              error,
              "Could not send the reset link. Please try again.",
            ),
          );
        }
      },
    });
  }

  function validatePasswordForm(): boolean {
    clearConfirmErrors();

    if (!newPassword) {
      setPasswordError("Please enter a new password.");
      return false;
    }
    if (newPassword.length < 8) {
      setPasswordError("Password must be at least 8 characters.");
      return false;
    }
    if (!confirmPassword) {
      setPasswordError("Please confirm your new password.");
      return false;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("Passwords do not match.");
      return false;
    }
    return true;
  }

  async function handleConfirmReset() {
    if (!validatePasswordForm()) return;

    confirmReset.mutate(
      { token: token ?? "", new_password: newPassword },
      {
        onSuccess: () => {
          resetCsrfToken();
          setResetComplete(true);
          redirectTimerRef.current = setTimeout(() => {
            navigate({ to: "/signin" });
          }, 2400);
        },
        onError: (error) => {
          const code = extractCode(error);
          const errs = extractFieldErrors(error);

          if (
            code === "invalid_or_expired_reset_token" ||
            code === "InvalidOrExpiredResetToken"
          ) {
            setPasswordError(
              "This reset link is invalid or has expired. Please request a new link.",
            );
          } else if (
            code === "password_reset_rate_limited" ||
            code === "PasswordResetRateLimited"
          ) {
            setPasswordError(
              "Too many password reset attempts. Please wait a while before trying again.",
            );
          } else if (code === "weak_password" || code === "WeakPassword") {
            setFieldErrors(errs);
            setPasswordError(extractDetail(error, "Password is too weak."));
          } else {
            setPasswordError(
              extractDetail(
                error,
                "Could not reset your password. Please try again.",
              ),
            );
          }
        },
      },
    );
  }

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (redirectTimerRef.current) {
        clearTimeout(redirectTimerRef.current);
      }
    };
  }, []);

  return (
    <div className="flex items-center justify-center min-h-screen">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>
            {hasToken ? "Set a new password" : "Reset your password"}
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            {hasToken
              ? "Choose a new password for your account."
              : "Enter your email and we'll send you a reset link."}
          </p>
        </CardHeader>
        <CardContent>
          {!hasToken ? (
            // --- Request mode: send reset link ---
            !requestSuccess ? (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleRequestReset();
                }}
                className="space-y-4"
              >
                <div className="space-y-1">
                  <Label htmlFor="reset-email">Email address</Label>
                  <Input
                    id="reset-email"
                    type="email"
                    placeholder="name@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    autoFocus
                  />
                </div>

                {requestError && (
                  <p className="text-sm text-destructive">{requestError}</p>
                )}

                <Button
                  type="submit"
                  className="w-full"
                  disabled={requestReset.isPending}
                >
                  {requestReset.isPending ? "Sending..." : "Send reset link"}
                </Button>

                <p className="text-center text-sm text-muted-foreground">
                  <Link
                    to="/signin"
                    className="text-primary hover:underline inline-flex items-center"
                  >
                    <ArrowLeft className="mr-1 size-3" />
                    Back to login
                  </Link>
                </p>
              </form>
            ) : (
              // Request success
              <div className="space-y-4 text-center">
                <CheckCircle className="mx-auto size-12 text-green-600" />
                <p className="text-sm text-muted-foreground">
                  If an account exists for that email, a reset link has been
                  sent.
                </p>
                <Button variant="outline" className="w-full" asChild>
                  <Link to="/signin">Back to login</Link>
                </Button>
              </div>
            )
          ) : !resetComplete ? (
            // --- Confirm mode: set new password ---
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleConfirmReset();
              }}
              className="space-y-4"
            >
              <div className="space-y-1">
                <Label htmlFor="new-password">New password</Label>
                <Input
                  id="new-password"
                  type={showPassword ? "text" : "password"}
                  placeholder="At least 8 characters"
                  value={newPassword}
                  onChange={(e) => {
                    setNewPassword(e.target.value);
                    clearConfirmErrors();
                  }}
                  autoFocus
                />
              </div>

              <div className="space-y-1">
                <Label htmlFor="confirm-password">Confirm password</Label>
                <Input
                  id="confirm-password"
                  type={showPassword ? "text" : "password"}
                  placeholder="Repeat password"
                  value={confirmPassword}
                  onChange={(e) => {
                    setConfirmPassword(e.target.value);
                    clearConfirmErrors();
                  }}
                />
              </div>

              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setShowPassword(!showPassword)}
                className="gap-1"
              >
                {showPassword ? (
                  <EyeOff className="size-4" />
                ) : (
                  <Eye className="size-4" />
                )}
                <span className="text-xs">
                  {showPassword ? "Hide" : "Show"} passwords
                </span>
              </Button>

              {passwordError && (
                <p className="text-sm text-destructive">{passwordError}</p>
              )}

              {fieldErrors.length > 0 && (
                <ul className="text-sm text-destructive space-y-1">
                  {fieldErrors.map((msg, i) => (
                    <li key={i}>{msg}</li>
                  ))}
                </ul>
              )}

              <Button
                type="submit"
                className="w-full"
                disabled={confirmReset.isPending}
              >
                {confirmReset.isPending ? "Updating..." : "Update password"}
              </Button>

              <p className="text-center text-sm text-muted-foreground">
                <Link
                  to="/signin"
                  className="text-primary hover:underline inline-flex items-center"
                >
                  <ArrowLeft className="mr-1 size-3" />
                  Back to login
                </Link>
              </p>
            </form>
          ) : (
            // Confirm success
            <div className="space-y-4 text-center">
              <CheckCircle className="mx-auto size-12 text-green-600" />
              <p className="font-medium">Password reset successful</p>
              <p className="text-sm text-muted-foreground">
                Please log in with your new password.
              </p>
              <Button variant="outline" className="w-full" asChild>
                <Link to="/signin">Back to login</Link>
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
