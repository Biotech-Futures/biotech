import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";
import { StarIcon, MailIcon, MailCheckIcon, SearchIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useFinalists, useToggleFinalist } from "@/query/grading";

export const Route = createFileRoute("/_auth/grading/finalists")({
  component: FinalistsPage,
});

function FinalistsPage() {
  const q = useFinalists();
  const toggle = useToggleFinalist();
  const [groupId, setGroupId] = useState("");
  const [notify, setNotify] = useState(false);

  const addFinalist = () => {
    const n = Number(groupId);
    if (!Number.isFinite(n) || n <= 0) {
      toast.error("Enter a numeric group ID");
      return;
    }
    toggle.mutate(
      { groupId: n, flagged: true, notify },
      {
        onSuccess: () => {
          setGroupId("");
          toast.success(
            notify ? "Finalist flagged + notification queued" : "Finalist flagged",
          );
        },
        onError: (e: unknown) => toast.error((e as Error).message),
      },
    );
  };

  const removeFinalist = (id: number) => {
    toggle.mutate(
      { groupId: id, flagged: false },
      {
        onSuccess: () => toast.success("Finalist removed"),
        onError: (e: unknown) => toast.error((e as Error).message),
      },
    );
  };

  return (
    <div className="max-w-3xl space-y-4">
      <section className="space-y-2 rounded-md border p-4">
        <h3 className="font-semibold flex items-center gap-2">
          <StarIcon className="size-4" /> Add finalist
        </h3>
        <p className="text-sm text-muted-foreground">
          Look up group IDs from the group marking page or the Django admin.
        </p>
        <div className="flex flex-wrap items-center gap-8">
          <div className="relative w-40">
            <SearchIcon className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-[calc(50%+2px)] size-4 text-muted-foreground" />
            <Input
              type="number"
              min={1}
              placeholder="Group ID"
              value={groupId}
              onChange={(e) => setGroupId(e.target.value)}
              className="pl-8 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
            />
          </div>
          <label className="text-sm flex items-center gap-1">
            <input
              type="checkbox"
              checked={notify}
              onChange={(e) => setNotify(e.target.checked)}
            />
            Send notification email
          </label>
          <Button onClick={addFinalist} disabled={toggle.isPending}>
            Flag as finalist
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          Email requires <code>GRADING_FINALIST_EMAIL_ENABLED=true</code> on the
          backend; otherwise the flag is set but no email is sent (safe default).
        </p>
      </section>

      <section className="space-y-2">
        <h3 className="font-semibold">Current finalists</h3>
        {q.isPending ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : q.isError || !q.data ? (
          <p className="text-destructive">Failed to load.</p>
        ) : (
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Group</TableHead>
                  <TableHead>Flagged at</TableHead>
                  <TableHead>Notified</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {q.data.finalists.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={4} className="h-16 text-center text-muted-foreground">
                      No finalists yet.
                    </TableCell>
                  </TableRow>
                ) : (
                  q.data.finalists.map((f) => (
                    <TableRow key={f.group_id}>
                      <TableCell className="font-medium">
                        {f.group_name}{" "}
                        <span className="text-xs text-muted-foreground">#{f.group_id}</span>
                      </TableCell>
                      <TableCell>{new Date(f.flagged_at).toLocaleString()}</TableCell>
                      <TableCell>
                        {f.notified ? (
                          <span className="inline-flex items-center gap-1 text-emerald-700">
                            <MailCheckIcon className="size-4" /> Sent
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-muted-foreground">
                            <MailIcon className="size-4" /> —
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => removeFinalist(f.group_id)}
                          disabled={toggle.isPending}
                        >
                          Remove
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        )}
      </section>

    </div>
  );
}
