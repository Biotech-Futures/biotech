import { useState } from "react";
import { toast } from "sonner";
import { UploadIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { useBulkUploadMarks } from "@/query/grading";
import type { BulkUploadResponse } from "@/type/grading";

interface Props {
  code: string;
}

// Two-step flow:
//   1. Pick a file → POST dry_run=true → show diff summary + errors table.
//   2. If no errors, "Apply" → POST dry_run=false → toast, close, cache invalidates.
// Kept in a single dialog rather than a wizard: fewer clicks, admin can
// swap the file and re-preview in place.
export function BulkUploadDialog({ code }: Props) {
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<BulkUploadResponse | null>(null);
  const mut = useBulkUploadMarks();

  const reset = () => {
    setFile(null);
    setPreview(null);
  };

  const doPreview = () => {
    if (!file) return;
    setPreview(null);
    mut.mutate(
      { code, file, dryRun: true },
      {
        onSuccess: (data) => setPreview(data),
        onError: (e: unknown) => toast.error(`Preview failed: ${(e as Error).message}`),
      },
    );
  };

  const doApply = () => {
    if (!file || !preview || preview.summary.errors > 0) return;
    mut.mutate(
      { code, file, dryRun: false },
      {
        onSuccess: (data) => {
          toast.success(`Applied — wrote ${data.written ?? 0} rows`);
          setOpen(false);
          reset();
        },
        onError: (e: unknown) => toast.error(`Apply failed: ${(e as Error).message}`),
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) reset(); }}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <UploadIcon className="size-4" /> Upload marks
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Upload marks — {code}</DialogTitle>
          <DialogDescription>
            XLSX or CSV with columns: <code>group_id</code>, <code>criterion_id</code>,
            <code> mark</code>, <code>comment</code>. Extra columns are ignored.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <Input
            type="file"
            accept=".xlsx,.csv"
            onChange={(e) => {
              const f = e.target.files?.[0] ?? null;
              setFile(f);
              setPreview(null);
            }}
          />

          {preview ? <PreviewPanel preview={preview} /> : null}
        </div>

        <DialogFooter className="gap-2">
          <Button
            variant="outline"
            onClick={doPreview}
            disabled={!file || mut.isPending}
          >
            {mut.isPending && !preview ? "Previewing…" : "Preview"}
          </Button>
          <Button
            onClick={doApply}
            disabled={
              !preview || preview.summary.errors > 0 || mut.isPending
            }
          >
            {mut.isPending && preview ? "Applying…" : "Apply"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function PreviewPanel({ preview }: { preview: BulkUploadResponse }) {
  const { summary, errors } = preview;
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2 text-sm">
        <Badge label="creates" value={summary.creates} tone="emerald" />
        <Badge label="updates" value={summary.updates} tone="amber" />
        <Badge label="unchanged" value={summary.unchanged} tone="muted" />
        <Badge label="errors" value={summary.errors} tone={summary.errors > 0 ? "red" : "muted"} />
      </div>

      {errors.length > 0 ? (
        <div className="max-h-48 overflow-auto rounded-md border">
          <table className="w-full text-sm">
            <thead className="bg-muted text-left">
              <tr>
                <th className="p-2 w-20">Row</th>
                <th className="p-2">Error</th>
              </tr>
            </thead>
            <tbody>
              {errors.map((e, i) => (
                <tr key={i} className="border-t">
                  <td className="p-2 font-mono">{e.row}</td>
                  <td className="p-2">{e.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {summary.errors > 0 ? (
        <p className="text-xs text-destructive">
          Fix the errors and re-upload before applying.
        </p>
      ) : null}
    </div>
  );
}

function Badge({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "emerald" | "amber" | "red" | "muted";
}) {
  const cls = {
    emerald: "bg-emerald-100 text-emerald-800",
    amber: "bg-amber-100 text-amber-800",
    red: "bg-red-100 text-red-800",
    muted: "bg-muted text-muted-foreground",
  }[tone];
  return (
    <span className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium ${cls}`}>
      <span>{label}</span>
      <span className="font-mono">{value}</span>
    </span>
  );
}
