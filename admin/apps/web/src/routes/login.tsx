import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { useAuth } from "@/lib/mock-auth";
import { toast } from "sonner";

export const Route = createFileRoute("/login")({
  component: LoginPage,
});

function LoginPage() {
  const navigate = useNavigate();
  const { accounts, isAuthenticated, isHydrated, login, user } = useAuth();
  const [email, setEmail] = useState(accounts[0]?.email ?? "");
  const [password, setPassword] = useState(accounts[0]?.password ?? "");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const accountHints = useMemo(
    () =>
      accounts.map((account) => ({
        email: account.email,
        password: account.password,
        name: account.user.name,
        team: account.user.team,
      })),
    [accounts],
  );

  useEffect(() => {
    if (isHydrated && isAuthenticated) {
      void navigate({ to: "/" });
    }
  }, [isAuthenticated, isHydrated, navigate]);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);

    try {
      await login(email, password);
      toast.success("Mock login successful.");
      void navigate({ to: "/" });
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unable to sign in right now.";
      toast.error(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!isHydrated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top,_rgba(79,184,178,0.25),_transparent_42%),linear-gradient(180deg,#f5fbf8_0%,#e7f3ec_100%)]">
        <div className="rounded-2xl border bg-card/90 px-6 py-4 text-sm text-muted-foreground shadow-sm">
          Restoring session...
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(79,184,178,0.22),_transparent_38%),radial-gradient(circle_at_bottom_right,_rgba(47,106,74,0.18),_transparent_32%),linear-gradient(180deg,#f7fcf8_0%,#e7f3ec_100%)] px-6 py-10">
      <div className="mx-auto grid min-h-[calc(100vh-5rem)] max-w-6xl gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <section className="relative overflow-hidden rounded-[2rem] border bg-white/80 p-8 shadow-[0_30px_80px_rgba(23,58,64,0.12)] backdrop-blur">
          <div className="absolute inset-x-8 top-0 h-px bg-gradient-to-r from-transparent via-emerald-300/70 to-transparent" />
          <Badge variant="outline">BioTech Futures Admin</Badge>
          <h1 className="mt-5 max-w-xl text-4xl font-semibold tracking-tight text-[var(--sea-ink)]">
            Sign in to the mock operations console.
          </h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-[var(--sea-ink-soft)]">
            This login is intentionally local-only for architecture demo purposes. It matches the admin
            site style and lets us test protected routes before the real auth flow is connected.
          </p>

          <div className="mt-8 grid gap-4 md:grid-cols-3">
            <InfoCard title="Session model" body="Local storage backed mock auth with protected admin routes." />
            <InfoCard title="Next integration" body="Swap the mock provider for real session and role checks later." />
            <InfoCard title="Current scope" body="No database required, but the login flow behaves like a real entry point." />
          </div>

          <div className="mt-10 rounded-3xl border bg-[linear-gradient(135deg,rgba(79,184,178,0.09),rgba(47,106,74,0.06))] p-6">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-[var(--sea-ink)]">Demo accounts</p>
                <p className="text-sm text-[var(--sea-ink-soft)]">
                  Click a card to autofill the credentials.
                </p>
              </div>
              {user ? <Badge variant="secondary">Signed in as {user.name}</Badge> : null}
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              {accountHints.map((account) => (
                <button
                  key={account.email}
                  type="button"
                  onClick={() => {
                    setEmail(account.email);
                    setPassword(account.password);
                  }}
                  className="rounded-2xl border bg-white/80 p-4 text-left transition hover:-translate-y-0.5 hover:shadow-sm"
                >
                  <p className="text-sm font-semibold text-[var(--sea-ink)]">{account.name}</p>
                  <p className="mt-1 text-xs uppercase tracking-[0.2em] text-[var(--kicker)]">
                    {account.team}
                  </p>
                  <p className="mt-4 text-sm text-[var(--sea-ink-soft)]">{account.email}</p>
                  <p className="mt-1 text-sm text-[var(--sea-ink-soft)]">Password: {account.password}</p>
                </button>
              ))}
            </div>
          </div>
        </section>

        <section className="rounded-[2rem] border bg-white/92 p-8 shadow-[0_28px_70px_rgba(23,58,64,0.14)] backdrop-blur">
          <div className="mx-auto max-w-md">
            <p className="text-sm font-medium uppercase tracking-[0.24em] text-[var(--kicker)]">
              Admin Sign In
            </p>
            <h2 className="mt-3 text-2xl font-semibold text-[var(--sea-ink)]">Welcome back</h2>
            <p className="mt-2 text-sm leading-6 text-[var(--sea-ink-soft)]">
              Use one of the demo identities on the left, or type the credentials directly here.
            </p>

            <form className="mt-8 space-y-5" onSubmit={onSubmit}>
              <div className="space-y-2">
                <Label htmlFor="login-email">Email</Label>
                <Input
                  id="login-email"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="admin@biotech.demo"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="login-password">Password</Label>
                <Input
                  id="login-password"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Enter password"
                />
              </div>

              <div className="rounded-2xl border bg-emerald-50/70 p-4 text-sm text-[var(--sea-ink-soft)]">
                This is a mock login flow. It protects routes and simulates a signed-in admin without
                requiring a real database or auth backend.
              </div>

              <Button type="submit" className="w-full" disabled={isSubmitting}>
                {isSubmitting ? "Signing in..." : "Sign In"}
              </Button>
            </form>
          </div>
        </section>
      </div>
    </div>
  );
}

function InfoCard({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-2xl border bg-white/70 p-4">
      <p className="text-sm font-semibold text-[var(--sea-ink)]">{title}</p>
      <p className="mt-2 text-sm leading-6 text-[var(--sea-ink-soft)]">{body}</p>
    </div>
  );
}
