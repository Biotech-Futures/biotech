import { Link } from "@tanstack/react-router";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Controller, useForm, useWatch } from "react-hook-form";
import z from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { AlertTriangleIcon } from "lucide-react";
import { AuthError, useMagicLinkSignIn, usePasswordSignIn } from "@/fetch/auth";
import { useSendCooldown } from "@/hooks/use-send-cooldown";
import { BRAND_CONNECT, SUPPORT_EMAIL } from "@/lib/brand";

type LoginMode = "password" | "magic";

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().optional(),
});

export function LoginForm({
  className,
  ...props
}: React.ComponentProps<"div">) {
  const [mode, setMode] = useState<LoginMode>("password");
  const { control, handleSubmit } = useForm<z.infer<typeof loginSchema>>({
    defaultValues: {
      email: "",
      password: "",
    },
    resolver: zodResolver(loginSchema),
  });

  const {
    mutate: sendMagicLink,
    isPending: isMagicLinkPending,
    error: magicLinkError,
    reset: resetMagicLink,
  } = useMagicLinkSignIn();
  const {
    mutate: signInWithPassword,
    isPending: isPasswordPending,
    error: passwordError,
    reset: resetPasswordSignIn,
  } = usePasswordSignIn();
  const isPending = isMagicLinkPending || isPasswordPending;

  // The backend enforces a 60s gap between sends; mirroring it here stops the
  // admin from stacking up codes they can't tell apart while mail is in transit.
  // Keyed per address to match the server — otherwise fixing a typo'd email
  // leaves you blocked client-side for one the server would happily serve.
  const emailValue = useWatch({ control, name: "email" }) ?? "";
  const magicCooldown = useSendCooldown(
    `magic-link:${emailValue.trim().toLowerCase()}`,
  );
  const magicBlocked = mode === "magic" && magicCooldown.secondsLeft > 0;

  // The toast disappears after a few seconds; a blocked admin needs the next step to stay put.
  const isAccountInactive = [magicLinkError, passwordError].some(
    (error) => error instanceof AuthError && error.code === "account_inactive",
  );

  return (
    <div
      className={cn("flex w-full max-w-md min-w-0 flex-col gap-6", className)}
      {...props}
    >
      <form
        onSubmit={handleSubmit((data) => {
          // Each mutation keeps its last error until it reruns, so drop the
          // other one's — the panel must reflect this attempt only.
          if (mode === "magic") {
            if (magicBlocked) return;
            resetPasswordSignIn();
            sendMagicLink(data.email, {
              // Hold the button either way: on 429 the server tells us how long,
              // and on a dropped connection the send may still have gone through.
              onSuccess: () => magicCooldown.start(),
              onError: (error) =>
                magicCooldown.start(
                  error instanceof AuthError ? error.retryAfter : undefined,
                ),
            });
            return;
          }

          resetMagicLink();
          signInWithPassword({
            email: data.email,
            password: data.password ?? "",
          });
        })}
      >
        <FieldGroup>
          <div className="flex flex-col items-center gap-2 text-center">
            <a
              href="#"
              className="flex flex-col items-center gap-2 font-medium"
            >
              <div className="flex items-center justify-center rounded-md">
                <img
                  src="/logo.png"
                  alt={`${BRAND_CONNECT} Logo`}
                  width={40}
                  height={40}
                />
                {/* <GalleryVerticalEndIcon className="size-6" /> */}
              </div>
              <span className="sr-only">{BRAND_CONNECT}</span>
            </a>
            <h1 className="text-xl font-bold">Welcome to {BRAND_CONNECT}</h1>
          </div>

          <div className="grid grid-cols-2 gap-2 rounded-md bg-muted p-1">
            <Button
              type="button"
              variant={mode === "password" ? "secondary" : "ghost"}
              className="h-9"
              onClick={() => setMode("password")}
            >
              Password
            </Button>
            <Button
              type="button"
              variant={mode === "magic" ? "secondary" : "ghost"}
              className="h-9"
              onClick={() => setMode("magic")}
            >
              Magic link
            </Button>
          </div>

          <Controller
            name="email"
            control={control}
            render={({ field }) => (
              <Field>
                <FieldLabel htmlFor="email" requiredMarker>
                  Email
                </FieldLabel>
                <Input
                  id="email"
                  type="email"
                  placeholder="m@example.com"
                  className="h-10"
                  required
                  {...field}
                />
              </Field>
            )}
          />

          {mode === "password" && (
            <Controller
              name="password"
              control={control}
              render={({ field }) => (
                <Field>
                  <div className="flex items-center justify-between">
                    <FieldLabel htmlFor="password" requiredMarker>
                      Password
                    </FieldLabel>
                    <Link
                      to="/reset-password"
                      search={{ token: undefined }}
                      className="text-xs text-muted-foreground hover:text-primary hover:underline"
                    >
                      Forgot your password?
                    </Link>
                  </div>
                  <Input
                    id="password"
                    type="password"
                    autoComplete="current-password"
                    className="h-10"
                    required
                    {...field}
                  />
                </Field>
              )}
            />
          )}

          {isAccountInactive && (
            <div
              role="alert"
              className="flex items-start gap-3 rounded-xl border border-destructive/50 bg-destructive/5 p-4 text-sm"
            >
              <AlertTriangleIcon className="mt-0.5 size-4 shrink-0 text-destructive" />
              <div className="space-y-2">
                <p className="font-medium text-destructive">Account inactive</p>
                <p className="text-muted-foreground">
                  Your account has been suspended or deactivated. An
                  administrator needs to reactivate it before you can sign in.
                </p>
                <a
                  href={`mailto:${SUPPORT_EMAIL}`}
                  className="inline-block font-medium underline underline-offset-4"
                >
                  {SUPPORT_EMAIL}
                </a>
              </div>
            </div>
          )}

          <Field>
            <Button
              type="submit"
              size="lg"
              loading={isPending}
              disabled={magicBlocked}
              className="w-full"
            >
              {mode === "password"
                ? "Login"
                : magicBlocked
                  ? `Resend in ${magicCooldown.secondsLeft}s`
                  : "Send magic link"}
            </Button>
          </Field>
        </FieldGroup>
      </form>
      <FieldDescription className="px-6 text-center">
        {mode === "password"
          ? "Use your account email and password."
          : "We will email you a one-time sign-in link."}
      </FieldDescription>
    </div>
  );
}
