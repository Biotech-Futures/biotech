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
import type { ImportRowError } from "@/query/user";
import { toast } from "sonner";

export type ImportResult = {
  created: number;
  skipped: { email: string; reason: string }[];
};

interface CsvImportSheetProps<TRow> {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  /** Singular noun for the rows, e.g. "mentor" / "student". */
  noun: string;
  /** Parse raw CSV into valid rows + per-row errors. Throws for a wrong file. */
  parse: (text: string) => { valid: TRow[]; invalid: ImportRowError[] };
  /** Send valid rows to the backend; returns created count + skipped reasons. */
  onImport: (rows: TRow[]) => Promise<ImportResult>;
  rowKey: (row: TRow) => string;
  rowPrimary: (row: TRow) => { name: string; email: string; note?: string };
  rowBadges: (row: TRow) => string[];
}

/**
 * Shared CSV-import dialog used by the Students and Mentors tabs: file picker,
 * valid-rows preview, invalid-rows-with-reasons list, and an after-import
 * created/skipped results panel. Fails gracefully — a wrong/empty file shows a
 * clear message and one bad row never blocks the rest.
 */
export function CsvImportSheet<TRow>({
  open,
  onOpenChange,
  title,
  description,
  noun,
  parse,
  onImport,
  rowKey,
  rowPrimary,
  rowBadges,
}: CsvImportSheetProps<TRow>) {
  const [file, setFile] = useState<File | null>(null);
  const [valid, setValid] = useState<TRow[]>([]);
  const [invalid, setInvalid] = useState<ImportRowError[]>([]);
  const [fileError, setFileError] = useState<string | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [importing, setImporting] = useState(false);

  const reset = () => {
    setFile(null);
    setValid([]);
    setInvalid([]);
    setFileError(null);
    setResult(null);
  };

  const handleOpenChange = (next: boolean) => {
    if (!next) reset();
    onOpenChange(next);
  };

  const handleChooseFile = async (selected: File | null) => {
    setFile(selected);
    setValid([]);
    setInvalid([]);
    setFileError(null);
    setResult(null);
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
    setImporting(true);
    try {
      const res = await onImport(valid);
      setResult(res);
      toast.success(
        `Imported ${res.created} ${noun}${res.created === 1 ? "" : "s"}${
          res.skipped.length ? `, ${res.skipped.length} skipped` : ""
        }.`,
      );
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Import failed — nothing was saved.",
      );
    } finally {
      setImporting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="flex max-h-[92vh] flex-col overflow-hidden sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 pb-4">
          <div className="space-y-1.5">
            <Label htmlFor="csv-import-file">CSV file</Label>
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
              <div className="border-b px-4 py-2 text-sm font-medium">
                Preview
              </div>
              <div className="max-h-64 space-y-2 overflow-auto px-4 py-3 text-sm">
                {valid.slice(0, 8).map((row) => {
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
                {valid.length > 8 ? (
                  <p className="text-xs text-muted-foreground">
                    Showing the first 8 of {valid.length} rows.
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
            <div className="rounded-md border border-primary/30 bg-primary/5">
              <div className="border-b px-4 py-2 text-sm font-medium">
                {result.created} created · {result.skipped.length} skipped
              </div>
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
            </div>
          ) : null}
        </div>

        <DialogFooter className="shrink-0 border-t">
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            {result ? "Close" : "Cancel"}
          </Button>
          <Button
            onClick={handleImport}
            loading={importing}
            disabled={!valid.length || result !== null}
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
