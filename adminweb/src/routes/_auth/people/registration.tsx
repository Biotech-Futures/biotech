import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { AlertCircleIcon, LoaderCircleIcon } from "lucide-react";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { resolveRegistrationIntakeUrl } from "@/lib/registrationIntakeUrl";

export const Route = createFileRoute("/_auth/people/registration")({
  component: RegistrationPage,
});

function RegistrationPage() {
  const registrationUrl = resolveRegistrationIntakeUrl(
    import.meta.env.VITE_REGISTRATION_INTAKE_URL,
  );
  const [isLoading, setIsLoading] = useState(true);

  if (registrationUrl.status !== "configured") {
    const isInvalid = registrationUrl.status === "invalid";

    return (
      <Card role="status" className="max-w-3xl">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircleIcon className="size-4 text-muted-foreground" />
            Registration intake unavailable
          </CardTitle>
          <CardDescription>
            {isInvalid
              ? "The configured registration intake URL is invalid. Use an HTTP or HTTPS URL."
              : "Set VITE_REGISTRATION_INTAKE_URL to make registration available in this portal."}
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <section aria-labelledby="registration-intake-heading" className="space-y-4">
      <div className="max-w-3xl space-y-1">
        <h2
          id="registration-intake-heading"
          className="text-base font-semibold tracking-tight"
        >
          Registration intake
        </h2>
        <p className="text-sm text-muted-foreground">
          This temporary tab opens the current intake while the next admin
          portal is prepared. Your signed-in Django session identifies you as
          the submitter.
        </p>
      </div>

      <div className="relative min-h-[36rem] overflow-hidden rounded-xl ring-1 ring-foreground/10">
        {isLoading && (
          <div
            role="status"
            className="absolute inset-0 z-10 flex min-h-[36rem] items-center justify-center gap-2 bg-background text-sm text-muted-foreground"
          >
            <LoaderCircleIcon className="size-4 animate-spin" aria-hidden="true" />
            Loading registration intake...
          </div>
        )}
        <iframe
          src={registrationUrl.url}
          title="Supervisor registration intake"
          referrerPolicy="strict-origin-when-cross-origin"
          className="block min-h-[36rem] w-full border-0 md:min-h-[calc(100vh-15rem)]"
          onLoad={() => setIsLoading(false)}
        />
      </div>
    </section>
  );
}
