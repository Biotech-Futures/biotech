import { createFileRoute, Link } from "@tanstack/react-router";
import { toast } from "sonner";
import { AlertTriangleIcon, CheckCircle2Icon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useMarksRelease, useToggleRelease } from "@/query/grading";

export const Route = createFileRoute("/_auth/grading/release")({
  component: ReleasePage,
});

function ReleasePage() {
  const q = useMarksRelease();
  const toggle = useToggleRelease();

  if (q.isPending) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }
  if (q.isError || !q.data) {
    return <p className="text-destructive">Failed to load release status.</p>;
  }

  const released = q.data.released_at != null;

  const flip = (release: boolean) =>
    toggle.mutate(
      { release },
      {
        onSuccess: (d) => toast.success(release ? `Released at ${d.released_at}` : "Marks unreleased"),
        onError: (e: unknown) => toast.error((e as Error).message),
      },
    );

  return (
    <div className="max-w-xl space-y-4">
      <div className={`rounded-md border p-4 flex items-start gap-3 ${released ? "bg-emerald-50 border-emerald-200" : "bg-amber-50 border-amber-200"}`}>
        {released ? (
          <CheckCircle2Icon className="size-5 text-emerald-600 mt-0.5" />
        ) : (
          <AlertTriangleIcon className="size-5 text-amber-600 mt-0.5" />
        )}
        <div className="space-y-1">
          <p className="font-medium">
            {released ? "Marks are released" : "Marks are NOT released"}
          </p>
          <p className="text-sm text-muted-foreground">
            {released
              ? `Released at ${q.data.released_at}${q.data.released_by ? ` by ${q.data.released_by}` : ""}.`
              : "Students and supervisors cannot see their grades until you release."}
          </p>
        </div>
      </div>

      <div className="flex gap-2">
        <Button
          disabled={toggle.isPending || released}
          onClick={() => flip(true)}
        >
          {released ? "Already released" : "Release now"}
        </Button>
        <Button
          variant="outline"
          disabled={toggle.isPending || !released}
          onClick={() => flip(false)}
        >
          Unrelease
        </Button>
        <Button asChild variant="ghost">
          <Link to="/grading">Back</Link>
        </Button>
      </div>
    </div>
  );
}
