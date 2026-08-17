import { createFileRoute, Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useQueryComponentRows } from "@/query/grading";
import { CheckCircle2Icon, CircleDashedIcon } from "lucide-react";

export const Route = createFileRoute("/_auth/grading/components/$code")({
  component: ComponentMarkingTablePage,
});

function ComponentMarkingTablePage() {
  const { code } = Route.useParams();
  const q = useQueryComponentRows(code);

  if (q.isPending) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }
  if (q.isError || !q.data) {
    return <p className="text-destructive">Failed to load component "{code}".</p>;
  }

  const { component, rows, criteria_total } = q.data;
  const submittedCount = rows.filter((r) => r.submission_id != null).length;
  const fullyMarkedCount = rows.filter(
    (r) => r.submission_id != null && criteria_total > 0 && r.criteria_graded >= criteria_total,
  ).length;

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between">
        <h2 className="text-xl font-semibold">{component.name}</h2>
        <div className="text-sm text-muted-foreground">
          {submittedCount}/{rows.length} submitted · {fullyMarkedCount}/{submittedCount} fully marked
        </div>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Group</TableHead>
              <TableHead>Submitted</TableHead>
              <TableHead>Late</TableHead>
              <TableHead>Progress</TableHead>
              <TableHead className="text-right">Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="h-24 text-center text-muted-foreground">
                  No groups.
                </TableCell>
              </TableRow>
            ) : (
              rows.map((r) => {
                const submitted = r.submission_id != null;
                const progressLabel = criteria_total > 0
                  ? `${r.criteria_graded}/${criteria_total}`
                  : "—";
                const done = submitted && criteria_total > 0 && r.criteria_graded >= criteria_total;
                return (
                  <TableRow key={r.group_id}>
                    <TableCell className="font-medium">{r.group_name}</TableCell>
                    <TableCell>
                      {submitted ? (
                        <span title={r.submitted_at ?? ""}>
                          {r.submitted_at ? new Date(r.submitted_at).toLocaleDateString() : "—"}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell>{r.is_late ? "Yes" : "—"}</TableCell>
                    <TableCell>
                      <span className="inline-flex items-center gap-1 text-sm">
                        {done ? (
                          <CheckCircle2Icon className="size-4 text-emerald-600" />
                        ) : (
                          <CircleDashedIcon className="size-4 text-muted-foreground" />
                        )}
                        {progressLabel}
                      </span>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button asChild variant="outline" size="sm" disabled={!submitted}>
                        <Link
                          to="/grading/components/$code/$groupId"
                          params={{ code, groupId: String(r.group_id) }}
                        >
                          {submitted ? "Open" : "No submission"}
                        </Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </div>

      <div>
        <Button asChild variant="ghost" size="sm">
          <Link to="/grading">Back</Link>
        </Button>
      </div>
    </div>
  );
}
