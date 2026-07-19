import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import {
  PAGE_SIZE_PRESETS,
  PageSizeSelect,
} from "@/components/user/PageSizeSelect";
import type { CsvTemplate, ImportRowError } from "@/query/user";
import { DownloadIcon } from "lucide-react";
import { toast } from "sonner";

export type ImportResult = {
  created: number;
  skipped: { email: string; reason: string }[];
  /** Set by the student importer: co-registered friends grouped at import time. */
  coRegistration?: {
    groupsCreated: { name: string; memberCount: number }[];
    warnings: string[];
  };
};

/** One import run, aggregated across every batch that was sent. */
type ImportSummary = ImportResult & {
  /** Rows in batches the server accepted; below `total` when a batch failed. */
  attempted: number;
  total: number;
  /** Set when a batch failed — earlier batches are already committed. */
  error?: string;
};

// The server creates users row by row (8-15 queries each), so the whole file in
// one request times out past roughly a thousand rows. ~100 rows per request
// stays well inside the gateway timeout and Django's 2.5 MB JSON body limit,
// while keeping the number of round-trips reasonable for a big file.
const IMPORT_BATCH_SIZE = 100;
const IMPORT_TOAST_ID = "csv-import";

/**
 * Split rows into sequential batches. Rows sharing a batch key always land in
 * the same batch: the backend only co-registers students created within a
 * single request, so slicing a group across batches would silently drop it. A
 * group bigger than the batch size ships oversized rather than being split.
 */
function batchRows<TRow>(
  rows: TRow[],
  batchKey?: (row: TRow) => string | undefined,
): TRow[][] {
  const units: TRow[][] = [];
  const byKey = new Map<string, TRow[]>();
  for (const row of rows) {
    const key = batchKey?.(row)?.trim();
    if (!key) {
      units.push([row]);
      continue;
    }
    const existing = byKey.get(key);
    if (existing) {
      existing.push(row);
      continue;
    }
    // Pushed by reference, so later members of the group grow this same unit.
    const unit = [row];
    byKey.set(key, unit);
    units.push(unit);
  }

  const batches: TRow[][] = [];
  let current: TRow[] = [];
  for (const unit of units) {
    if (current.length && current.length + unit.length > IMPORT_BATCH_SIZE) {
      batches.push(current);
      current = [];
    }
    current.push(...unit);
  }
  if (current.length) batches.push(current);
  return batches;
}

/**
 * Turn a failed batch POST into something an admin can act on.
 *
 * The server's message is row-numbered relative to the *batch*, so "Row 3" of
 * the 4th batch is really file row 303 — rebase it onto `rowsBefore` (the count
 * already imported) or the number sends them to the wrong line of the CSV.
 */
function batchErrorMessage(error: unknown, rowsBefore: number): string {
  const serverMsg = (error as { response?: { data?: { msg?: string } } })
    ?.response?.data?.msg;
  if (!serverMsg) {
    // Axios's own "Request failed with status code 400" tells the admin nothing.
    return "The server rejected a batch.";
  }
  return serverMsg.replace(
    /\bRow (\d+)\b/g,
    (_, n: string) => `Row ${rowsBefore + Number(n)}`,
  );
}

function toCsvCell(value: string): string {
  return /[",\r\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

function downloadTemplate(template: CsvTemplate) {
  const csv = [template.headers, template.sampleRow]
    .map((row) => row.map(toCsvCell).join(","))
    .join("\r\n");
  const url = URL.createObjectURL(
    new Blob([csv], { type: "text/csv;charset=utf-8" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = template.fileName;
  link.click();
  URL.revokeObjectURL(url);
}

const plural = (count: number, noun: string) =>
  `${count} ${noun}${count === 1 ? "" : "s"}`;

interface CsvImportSheetProps<TRow> {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  /** Singular noun for the rows, e.g. "mentor" / "student". */
  noun: string;
  /** Header + sample row for the "Download template" button. */
  template: CsvTemplate;
  /** Parse raw CSV into valid rows + per-row errors. Throws for a wrong file. */
  parse: (text: string) => { valid: TRow[]; invalid: ImportRowError[] };
  /** Send one batch of valid rows; returns created count + skipped reasons. */
  onImport: (rows: TRow[]) => Promise<ImportResult>;
  rowKey: (row: TRow) => string;
  rowPrimary: (row: TRow) => { name: string; email: string; note?: string };
  rowBadges: (row: TRow) => string[];
  /** Rows sharing this key must be imported together (student groupNumber). */
  batchGroupKey?: (row: TRow) => string | undefined;
}

/**
 * Shared CSV-import dialog used by the Students and Mentors tabs: file picker,
 * template download, valid-rows preview, invalid-rows-with-reasons list, and an
 * after-import created/skipped results panel. Large files are sent in
 * sequential batches — the import is therefore not atomic across batches, so a
 * mid-run failure is reported with exactly what was and wasn't saved.
 */
export function CsvImportSheet<TRow>({
  open,
  onOpenChange,
  title,
  description,
  noun,
  template,
  parse,
  onImport,
  rowKey,
  rowPrimary,
  rowBadges,
  batchGroupKey,
}: CsvImportSheetProps<TRow>) {
  const [file, setFile] = useState<File | null>(null);
  const [valid, setValid] = useState<TRow[]>([]);
  const [invalid, setInvalid] = useState<ImportRowError[]>([]);
  const [fileError, setFileError] = useState<string | null>(null);
  const [result, setResult] = useState<ImportSummary | null>(null);
  const [importing, setImporting] = useState(false);
  const [sent, setSent] = useState(0);
  const [previewSize, setPreviewSize] = useState<number>(PAGE_SIZE_PRESETS[0]);

  const reset = () => {
    setFile(null);
    setValid([]);
    setInvalid([]);
    setFileError(null);
    setResult(null);
    setSent(0);
  };

  const handleOpenChange = (next: boolean) => {
    if (!next) {
      // Closing mid-run would reset() into a discarded summary, leaving no
      // record of the batches that already committed server-side.
      if (importing) return;
      reset();
    }
    onOpenChange(next);
  };

  const handleChooseFile = async (selected: File | null) => {
    setFile(selected);
    setValid([]);
    setInvalid([]);
    setFileError(null);
    setResult(null);
    setSent(0);
    if (!selected) return;
    try {
      const text = await selected.text();
      const parsed = parse(text);
      setValid(parsed.valid);
      setInvalid(parsed.invalid);
    } catch (error) {
      setFileError(
        error instanceof Error ? error.message : "Failed to parse the CSV file.",
      );
    }
  };

  const handleImport = async () => {
    if (!valid.length) {
      toast.error(`No valid ${noun} rows to import.`);
      return;
    }
    const batches = batchRows(valid, batchGroupKey);
    const total = valid.length;
    const summary: ImportSummary = {
      created: 0,
      skipped: [],
      attempted: 0,
      total,
    };
    const groupsCreated: { name: string; memberCount: number }[] = [];
    const warnings: string[] = [];

    setImporting(true);
    setSent(0);
    setResult(null);
    try {
      // Sequential on purpose: the per-row server work is heavy, and parallel
      // batches would only make the timeouts they exist to avoid more likely.
      for (const batch of batches) {
        const res = await onImport(batch);
        summary.created += res.created;
        summary.skipped.push(...res.skipped);
        groupsCreated.push(...(res.coRegistration?.groupsCreated ?? []));
        warnings.push(...(res.coRegistration?.warnings ?? []));
        summary.attempted += batch.length;
        setSent(summary.attempted);
        if (batches.length > 1) {
          toast.loading(
            `Importing ${summary.attempted} / ${total} ${noun}s…`,
            { id: IMPORT_TOAST_ID },
          );
        }
      }
    } catch (error) {
      // Stop here: whatever broke this batch will almost certainly break the
      // rest, and every extra batch widens the "what actually saved?" gap.
      summary.error = batchErrorMessage(error, summary.attempted);
    }

    if (groupsCreated.length || warnings.length) {
      summary.coRegistration = { groupsCreated, warnings };
    }
    setResult(summary);
    setImporting(false);

    if (summary.error) {
      toast.error(
        `Import stopped — ${plural(summary.created, noun)} saved, ${plural(
          total - summary.attempted,
          "row",
        )} not sent.`,
        { id: IMPORT_TOAST_ID },
      );
      return;
    }
    toast.success(
      `Imported ${plural(summary.created, noun)}${
        summary.skipped.length ? `, ${summary.skipped.length} skipped` : ""
      }${
        groupsCreated.length
          ? `, ${plural(groupsCreated.length, "co-registration group")} created`
          : ""
      }.`,
      { id: IMPORT_TOAST_ID },
    );
    warnings.forEach((warning) => toast.warning(warning));
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        className="flex max-h-[92vh] flex-col overflow-hidden sm:max-w-2xl"
        showCloseButton={!importing}
        onEscapeKeyDown={(event) => {
          if (importing) event.preventDefault();
        }}
        onInteractOutside={(event) => {
          if (importing) event.preventDefault();
        }}
      >
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 pb-4">
          <div className="space-y-1.5">
            <div className="flex items-center justify-between gap-3">
              <Label htmlFor="csv-import-file">CSV file</Label>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => downloadTemplate(template)}
              >
                <DownloadIcon /> Download template
              </Button>
            </div>
            <Input
              id="csv-import-file"
              type="file"
              accept=".csv,text/csv"
              onChange={(event) =>
                handleChooseFile(event.target.files?.[0] ?? null)
              }
            />
            {file ? (
              <p className="text-xs text-muted-foreground">{file.name}</p>
            ) : null}
          </div>

          {fileError ? (
            <div
              role="alert"
              className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
            >
              {fileError}
            </div>
          ) : null}

          {!fileError && (valid.length > 0 || invalid.length > 0) ? (
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">{valid.length} ready</Badge>
              {invalid.length ? (
                <Badge variant="secondary">
                  {invalid.length} with problems
                </Badge>
              ) : null}
            </div>
          ) : null}

          {valid.length ? (
            <div className="rounded-md border">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b px-4 py-2 text-sm font-medium">
                Preview
                <PageSizeSelect
                  value={previewSize}
                  onChange={setPreviewSize}
                  disabled={importing}
                />
              </div>
              <div className="max-h-80 space-y-2 overflow-auto px-4 py-3 text-sm">
                {valid.slice(0, previewSize).map((row) => {
                  const primary = rowPrimary(row);
                  return (
                    <div
                      key={rowKey(row)}
                      className="flex items-center justify-between gap-3 rounded-md bg-muted/40 px-3 py-2"
                    >
                      <div className="min-w-0">
                        <p className="font-medium">{primary.name}</p>
                        <p className="truncate text-xs text-muted-foreground">
                          {primary.email}
                        </p>
                        {primary.note ? (
                          <p className="text-xs text-amber-700 dark:text-amber-400">
                            {primary.note}
                          </p>
                        ) : null}
                      </div>
                      <div className="flex flex-wrap justify-end gap-2">
                        {rowBadges(row).map((badge, index) => (
                          <Badge key={index} variant="outline">
                            {badge}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  );
                })}
                {valid.length > previewSize ? (
                  <p className="text-xs text-muted-foreground">
                    Showing the first {previewSize} of {valid.length} rows.
                  </p>
                ) : null}
              </div>
            </div>
          ) : null}

          {invalid.length ? (
            <div className="rounded-md border">
              <div className="border-b px-4 py-2 text-sm font-medium">
                {invalid.length} row{invalid.length === 1 ? "" : "s"} skipped
                (won&apos;t import)
              </div>
              <div className="max-h-40 space-y-1 overflow-auto px-4 py-3 text-sm">
                {invalid.map((err) => (
                  <div
                    key={`${err.rowNumber}-${err.email}`}
                    className="flex items-center justify-between gap-3"
                  >
                    <span className="text-muted-foreground">
                      Row {err.rowNumber} · {err.email}
                    </span>
                    <span className="text-right text-destructive">
                      {err.reason}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {result ? (
            <div
              className={
                result.error
                  ? "rounded-md border border-destructive/40 bg-destructive/5"
                  : "rounded-md border border-primary/30 bg-primary/5"
              }
            >
              <div className="border-b px-4 py-2 text-sm font-medium">
                {result.created} created · {result.skipped.length} skipped
                {result.coRegistration?.groupsCreated.length
                  ? ` · ${result.coRegistration.groupsCreated.length} co-registration group${
                      result.coRegistration.groupsCreated.length === 1 ? "" : "s"
                    }`
                  : ""}
              </div>
              {result.error ? (
                <div
                  role="alert"
                  className="space-y-1 border-b px-4 py-3 text-sm"
                >
                  <p className="font-medium text-destructive">
                    Import stopped after {result.attempted} of {result.total}{" "}
                    rows — this file was sent in batches, so it was not
                    all-or-nothing.
                  </p>
                  <p className="text-muted-foreground">
                    {plural(result.created, noun)} above were saved.{" "}
                    {result.total - result.attempted} row
                    {result.total - result.attempted === 1 ? " was" : "s were"}{" "}
                    never sent, and rows in the batch that failed may or may not
                    have been saved — check the {noun} list. Re-importing the
                    same file is safe: existing emails are skipped.
                  </p>
                  <p className="text-destructive">{result.error}</p>
                </div>
              ) : null}
              {result.skipped.length ? (
                <div className="max-h-40 space-y-1 overflow-auto px-4 py-3 text-sm">
                  {result.skipped.map((skip, index) => (
                    <div
                      key={`${skip.email}-${index}`}
                      className="flex items-center justify-between gap-3"
                    >
                      <span className="truncate text-muted-foreground">
                        {skip.email}
                      </span>
                      <span className="text-right text-destructive">
                        {skip.reason}
                      </span>
                    </div>
                  ))}
                </div>
              ) : null}
              {result.coRegistration?.groupsCreated.length ? (
                <div className="space-y-1 border-t px-4 py-3 text-sm">
                  {result.coRegistration.groupsCreated.map((group) => (
                    <div
                      key={group.name}
                      className="flex items-center justify-between gap-3"
                    >
                      <span className="truncate font-medium">{group.name}</span>
                      <span className="text-muted-foreground">
                        {group.memberCount} student
                        {group.memberCount === 1 ? "" : "s"}
                      </span>
                    </div>
                  ))}
                  {result.coRegistration.warnings.map((warning, index) => (
                    <p
                      key={index}
                      className="text-xs text-amber-700 dark:text-amber-400"
                    >
                      {warning}
                    </p>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>

        <DialogFooter className="shrink-0 border-t">
          {importing ? (
            <p className="text-xs text-muted-foreground sm:mr-auto sm:self-center">
              Importing {sent} / {valid.length}… don&apos;t close this dialog.
            </p>
          ) : null}
          <Button
            variant="outline"
            disabled={importing}
            onClick={() => handleOpenChange(false)}
          >
            {result ? "Close" : "Cancel"}
          </Button>
          <Button
            onClick={handleImport}
            loading={importing}
            // A finished import must not be re-submitted, but a stopped one has
            // rows that were never sent — the admin has to be able to retry.
            disabled={!valid.length || (result !== null && !result.error)}
          >
            Import {valid.length ? `${valid.length} ` : ""}
            {noun}
            {valid.length === 1 ? "" : "s"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
