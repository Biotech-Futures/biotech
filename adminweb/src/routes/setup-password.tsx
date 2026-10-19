import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import axios from "axios";
import { apiFetch } from "@/lib/myFetch";
import { useQueryClient } from "@tanstack/react-query";

export const Route = createFileRoute("/setup-password")({
  component: SetupPasswordPage,
});

function SetupPasswordPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [isPending, setIsPending] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }

    setIsPending(true);
    try {
      // The role-agnostic endpoint, not the admin-scoped twin at
      // /api/v1/admin/auth/set-password/. That one is behind IsAdminScoped, so
      // it answered 403 to exactly the people this page exists for: a support
      // agent whose account was just created and has no password yet. The
      // portal hit the same wall once and this endpoint is the fix it got.
      const res = await apiFetch.post<{ msg: string; data: boolean | null }>(
        "/set-password/",
        { password },
      );
      if (!res.data.data) {
        setError(res.data.msg || "Failed to set password.");
        return;
      }
      sessionStorage.setItem("pwChecked", "1");
      await queryClient.invalidateQueries({ queryKey: ["auth-user"] });
      void navigate({ to: "/" });
    } catch (err) {
      // What the server said, when it said anything. "Please try again" is a
      // lie for every refusal this endpoint makes — none of them get better on
      // a second attempt — and it was what a support agent saw on the 403 that
      // sent them here in the first place.
      const body = axios.isAxiosError(err)
        ? (err.response?.data as { msg?: string; error?: string } | undefined)
        : undefined;
      setError(
        body?.msg ?? body?.error ?? "Failed to set password. Please try again.",
      );
    } finally {
      setIsPending(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Set Your Password</CardTitle>
          <p className="text-sm text-muted-foreground">
            Please set a password to continue using the admin panel.
          </p>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1">
              <Label htmlFor="password" requiredMarker>
                New Password
              </Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 8 characters"
                autoFocus
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="confirm" requiredMarker>
                Confirm Password
              </Label>
              <Input
                id="confirm"
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder="Repeat password"
              />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" className="w-full" disabled={isPending}>
              {isPending ? "Setting..." : "Set Password"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
