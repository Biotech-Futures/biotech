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
  useJobStatus,
  useQueryComponentRows,
  useStartComponentDownload,
} from "@/query/grading";
import { CheckCircle2Icon, CircleDashedIcon, DownloadIcon } from "lucide-react";
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
      <div className="flex items-baseline justify-between gap-4 flex-wrap">
        <h2 className="text-xl font-semibold">{component.name}</h2>
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
          <BulkUploadDialog code={code} />
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
