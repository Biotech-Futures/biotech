
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
import { useMagicLinkSignIn } from "@/fetch/auth";

export function LoginForm({
  className,
  ...props
}: React.ComponentProps<"div">) {
  const { control, handleSubmit } = useForm({
    defaultValues: {
      email: "",
    },
    resolver: zodResolver(
      z.object({
        email: z.string().email(),
      }),
    ),
  });

  const { mutate, isPending } = useMagicLinkSignIn();

  return (
    <div className={cn("flex flex-col gap-6 min-w-lg", className)} {...props}>
      <form onSubmit={handleSubmit((data) => mutate(data.email))}>
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

          <Field>
            <Button
              type="submit"
              size="lg"
              loading={isPending}
              className="w-full"
            >
              Login
            </Button>
          </Field>
        </FieldGroup>
      </form>
      <FieldDescription className="px-6 text-center"></FieldDescription>
    </div>
  );
}
