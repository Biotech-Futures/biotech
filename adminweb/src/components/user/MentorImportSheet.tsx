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
  parseMentorCsv,
  type MentorImportRow,
  type ImportRowError,
} from "@/query/user";
import { useImportMentors } from "@/query/mentor";
import { toast } from "sonner";

interface MentorImportSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

type ImportResult = {
  created: number;
  skipped: { email: string; reason: string }[];
};

export function MentorImportSheet({ open, onOpenChange }: MentorImportSheetProps) {
  const [file, setFile] = useState<File | null>(null);
  const [valid, setValid] = useState<MentorImportRow[]>([]);
  const [invalid, setInvalid] = useState<ImportRowError[]>([]);
  const [fileError, setFileError] = useState<string | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const importMentors = useImportMentors();

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
      const parsed = parseMentorCsv(text);
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
      toast.error("No valid mentor rows to import.");
      return;
    }
    try {
      const res = await importMentors.mutateAsync(valid);
      const created = res.data?.created?.length ?? 0;
      const skipped = res.data?.skipped ?? [];
      setResult({ created, skipped });
      toast.success(
        `Imported ${created} mentor${created === 1 ? "" : "s"}${
          skipped.length ? `, ${skipped.length} skipped` : ""
        }.`,
      );
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Import failed — nothing was saved.",
      );
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="flex max-h-[92vh] flex-col overflow-hidden sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Import Mentors CSV</DialogTitle>
          <DialogDescription>
            Upload the mentor registration export (Email Address, First Name,
            Surname, Country, Region, Mentor Reason, Capacity, Area(s) of
            Interest, Background, Institution or Company). Existing emails are
            skipped.
          </DialogDescription>
        </DialogHeader>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 pb-4">
          <div className="space-y-1.5">
            <Label htmlFor="mentor-csv-file">CSV file</Label>
            <Input
              id="mentor-csv-file"
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
            <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
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
                {valid.slice(0, 8).map((row) => (
                  <div
                    key={row.email}
                    className="flex items-center justify-between gap-3 rounded-md bg-muted/40 px-3 py-2"
                  >
                    <div className="min-w-0">
                      <p className="font-medium">
                        {`${row.firstName} ${row.lastName}`.trim()}
                      </p>
                      <p className="truncate text-xs text-muted-foreground">
                        {row.email}
                      </p>
                      {row.backgroundNote ? (
                        <p className="text-xs text-amber-700 dark:text-amber-400">
                          {row.backgroundNote}
                        </p>
                      ) : null}
                    </div>
                    <div className="flex flex-wrap justify-end gap-2">
                      <Badge variant="outline">{row.state}</Badge>
                      <Badge variant="outline">
                        {row.mentorBackground ?? "no background"}
                      </Badge>
                      <Badge variant="outline">
                        cap {row.mentorMaxGroupCount}
                      </Badge>
                      <Badge variant="outline">
                        {row.interests.length} interests
                      </Badge>
                    </div>
                  </div>
                ))}
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
            loading={importMentors.isPending}
            disabled={!valid.length || result !== null}
          >
            Import {valid.length ? `${valid.length} ` : ""}
            Mentor{valid.length === 1 ? "" : "s"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
