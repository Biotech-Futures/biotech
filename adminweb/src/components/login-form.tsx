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
import { Controller, useForm } from "react-hook-form";
import z from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useMagicLinkSignIn, usePasswordSignIn } from "@/fetch/auth";

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

  const { mutate: sendMagicLink, isPending: isMagicLinkPending } =
    useMagicLinkSignIn();
  const { mutate: signInWithPassword, isPending: isPasswordPending } =
    usePasswordSignIn();
  const isPending = isMagicLinkPending || isPasswordPending;

  return (
    <div
      className={cn("flex w-full max-w-md min-w-0 flex-col gap-6", className)}
      {...props}
    >
      <form
        onSubmit={handleSubmit((data) => {
          if (mode === "magic") {
            sendMagicLink(data.email);
            return;
          }

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
                  alt="BioTech Logo"
                  width={40}
                  height={40}
                />
                {/* <GalleryVerticalEndIcon className="size-6" /> */}
              </div>
              <span className="sr-only">BioTech</span>
            </a>
            <h1 className="text-xl font-bold">Welcome to BioTech</h1>
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
                <FieldLabel htmlFor="email">Email</FieldLabel>
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
                    <FieldLabel htmlFor="password">Password</FieldLabel>
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

          <Field>
            <Button
              type="submit"
              size="lg"
              loading={isPending}
              className="w-full"
            >
              {mode === "password" ? "Login" : "Send magic link"}
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
