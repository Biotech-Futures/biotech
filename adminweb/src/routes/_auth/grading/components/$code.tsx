import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  SortableTableHead,
  useSortableRows,
} from "@/components/ui/sortable-table";
import {
  useJobStatus,
  useQueryComponentRows,
  useStartComponentDownload,
} from "@/query/grading";
import { CheckCircle2Icon, CircleDashedIcon, DownloadIcon, UsersIcon } from "lucide-react";
import { toast } from "sonner";
import { BulkUploadDialog } from "@/components/grading/BulkUploadDialog";

export const Route = createFileRoute("/_auth/grading/components/$code")({
  component: ComponentMarkingTablePage,
});

function ComponentMarkingTablePage() {
  const { code } = Route.useParams();
  const q = useQueryComponentRows(code);
  const startDownload = useStartComponentDownload();
  const [jobId, setJobId] = useState<number | null>(null);
  const [toastId, setToastId] = useState<string | number | null>(null);
  const jobQ = useJobStatus(jobId);

  // Watch the polled job: on done, dismiss the loading toast, redirect the
  // browser to the signed result URL so the file downloads. On failure,
  // surface the error. Either way, clear jobId so the next click starts a
  // fresh job.
  useEffect(() => {
    const s = jobQ.data?.status;
    if (s !== "done" && s !== "failed") return;
    if (toastId != null) toast.dismiss(toastId);
    if (s === "done" && jobQ.data?.download_url) {
      toast.success("Download ready");
      window.location.href = jobQ.data.download_url;
    } else {
      toast.error(`Download failed: ${jobQ.data?.error ?? "unknown"}`);
    }
    setJobId(null);
    setToastId(null);
  }, [jobQ.data, toastId]);

  const kickOffDownload = (format: "zip" | "xlsx") => {
    const id = toast.loading(`Preparing ${format.toUpperCase()}…`);
    setToastId(id);
    startDownload.mutate(
      { code, format },
      {
        onSuccess: (newJobId) => setJobId(newJobId),
        onError: (e: unknown) => {
          toast.dismiss(id);
          setToastId(null);
          toast.error(`Download failed: ${(e as Error).message}`);
        },
      },
    );
  };

  const rows = q.data?.rows ?? [];
  const criteria_total = q.data?.criteria_total ?? 0;

  const { sortState, setSortState, sortedRows } = useSortableRows(
    rows,
    { key: "time" as "id" | "time" | "progress", direction: "desc" as const },
    (r, key) => {
      if (key === "id") return r.group_id;
      if (key === "time") return r.submitted_at;
      if (key === "progress") return r.submission_id != null ? r.criteria_graded : null;
      return null;
    },
  );

  // Sorting by progress: keep unsubmitted rows pinned at the bottom regardless
  // of direction, so admins never mistake "0/N" for a legitimate low score.
  const displayRows = sortState.key === "progress"
    ? [
        ...sortedRows.filter((r) => r.submission_id != null),
        ...sortedRows.filter((r) => r.submission_id == null),
      ]
    : sortedRows;

  if (q.isPending) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }
  if (q.isError || !q.data) {
    return <p className="text-destructive">Failed to load component "{code}".</p>;
  }

  const { component } = q.data;
  const submittedCount = rows.filter((r) => r.submission_id != null).length;
  const fullyMarkedCount = rows.filter(
    (r) => r.submission_id != null && criteria_total > 0 && r.criteria_graded >= criteria_total,
  ).length;

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">{component.name}</h2>
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <div className="text-sm text-muted-foreground">
            {submittedCount}/{rows.length} submitted · {fullyMarkedCount}/{submittedCount} fully marked
          </div>
          <Button
            variant="outline"
            size="sm"
            disabled={jobId != null || startDownload.isPending}
            onClick={() => kickOffDownload("zip")}
          >
            <DownloadIcon className="size-4" />
            Zip
          </Button>
          {component.code === "SAQ" ? (
            <Button
              variant="outline"
              size="sm"
              disabled={jobId != null || startDownload.isPending}
              onClick={() => kickOffDownload("xlsx")}
            >
              <DownloadIcon className="size-4" />
              XLSX
            </Button>
          ) : null}
        </div>
        <BulkUploadDialog code={code} />
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>
                <SortableTableHead
                  label="ID"
                  sortKey="id"
                  sortState={sortState}
                  onSortChange={setSortState}
                />
              </TableHead>
              <TableHead>Group</TableHead>
              <TableHead>Submitted</TableHead>
              <TableHead>
                <SortableTableHead
                  label="Time"
                  sortKey="time"
                  sortState={sortState}
                  onSortChange={setSortState}
                />
              </TableHead>
              <TableHead>Late</TableHead>
              <TableHead>
                <SortableTableHead
                  label="Progress"
                  sortKey="progress"
                  sortState={sortState}
                  onSortChange={setSortState}
                />
              </TableHead>
              <TableHead>Marker</TableHead>
              <TableHead className="text-right">Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {displayRows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={8} className="h-24 text-center text-muted-foreground">
                  No groups.
                </TableCell>
              </TableRow>
            ) : (
              displayRows.map((r) => {
                const submitted = r.submission_id != null;
                const progressLabel = criteria_total > 0
                  ? `${r.criteria_graded}/${criteria_total}`
                  : "—";
                const done = submitted && criteria_total > 0 && r.criteria_graded >= criteria_total;
                return (
                  <TableRow key={r.group_id}>
                    <TableCell>{r.group_id}</TableCell>
                    <TableCell className="font-medium">{r.group_name}</TableCell>
                    <TableCell>
                      {submitted && r.submitted_at ? (
                        new Date(r.submitted_at).toLocaleDateString()
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell>
                      {submitted && r.submitted_at ? (
                        new Date(r.submitted_at).toLocaleTimeString()
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell>{r.is_late ? "Yes" : "—"}</TableCell>
                    <TableCell>
                      {submitted ? (
                        <span className="inline-flex items-center gap-1 text-sm">
                          {done ? (
                            <CheckCircle2Icon className="size-4 text-emerald-600" />
                          ) : (
                            <CircleDashedIcon className="size-4 text-muted-foreground" />
                          )}
                          {progressLabel}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell className="text-sm">
                      {r.last_grader_name ? (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span className="inline-flex items-center gap-1">
                              {r.last_grader_name}
                              {r.grader_names.length > 1 ? (
                                <UsersIcon className="size-3.5 text-muted-foreground" />
                              ) : null}
                            </span>
                          </TooltipTrigger>
                          <TooltipContent>
                            Marked by: {r.grader_names.join(", ")}
                          </TooltipContent>
                        </Tooltip>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      {submitted ? (
                        <Button asChild variant="outline" size="sm">
                          <Link
                            to="/grading/components/$code/$groupId"
                            params={{ code, groupId: String(r.group_id) }}
                          >
                            Open
                          </Link>
                        </Button>
                      ) : (
                        <span className="text-sm text-muted-foreground">No submission</span>
                      )}
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
