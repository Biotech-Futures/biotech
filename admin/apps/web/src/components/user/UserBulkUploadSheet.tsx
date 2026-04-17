import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { parseCsvUsers } from "@/query/user";
import type { CsvUserRow } from "@/type/user";

interface UserBulkUploadSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onImport: (rows: CsvUserRow[]) => Promise<void> | void;
  isPending?: boolean;
}

export function UserBulkUploadSheet({
  open,
  onOpenChange,
  onImport,
  isPending,
}: UserBulkUploadSheetProps) {
  const [file, setFile] = useState<File | null>(null);
  const [rows, setRows] = useState<CsvUserRow[]>([]);

  const stats = useMemo(() => {
    const inactive = rows.filter((row) => !row.active).length;
    const supervisors = rows.filter((row) => row.role === "supervisor").length;
    return {
      total: rows.length,
      inactive,
      supervisors,
    };
  }, [rows]);

  const handleChooseFile = async (selectedFile: File | null) => {
    setFile(selectedFile);
    if (!selectedFile) {
      setRows([]);
      return;
    }

    try {
      const text = await selectedFile.text();
      const parsed = parseCsvUsers(text);
      setRows(parsed);
    } catch (error) {
      setRows([]);
      window.alert(
        error instanceof Error ? error.message : "Failed to parse the CSV file.",
      );
    }
  };

  const handleImport = async () => {
    if (!rows.length) {
      window.alert("Please choose a valid CSV file first.");
      return;
    }

    await onImport(rows);
    setFile(null);
    setRows([]);
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>Bulk Upload Users</SheetTitle>
          <SheetDescription>
            Upload a CSV with columns `name,email,role,track,status`.
          </SheetDescription>
        </SheetHeader>

        <div className="space-y-4 px-4">
          <div className="space-y-1.5">
            <Label htmlFor="user-csv-file">CSV file</Label>
            <Input
              id="user-csv-file"
              type="file"
              accept=".csv,text/csv"
              onChange={(event) => handleChooseFile(event.target.files?.[0] ?? null)}
            />
            {file ? (
              <p className="text-xs text-muted-foreground">{file.name}</p>
            ) : null}
          </div>

          <div className="flex flex-wrap gap-2">
            <Badge variant="outline">{stats.total} rows</Badge>
            <Badge variant="outline">{stats.supervisors} supervisors</Badge>
            <Badge variant="outline">{stats.inactive} inactive</Badge>
          </div>

          <div className="rounded-md border">
            <div className="border-b px-4 py-2 text-sm font-medium">
              Preview
            </div>
            <div className="max-h-72 overflow-auto px-4 py-3 text-sm">
              {rows.length ? (
                <div className="space-y-2">
                  {rows.slice(0, 8).map((row) => (
                    <div
                      key={row.id}
                      className="flex items-center justify-between gap-3 rounded-md bg-muted/40 px-3 py-2"
                    >
                      <div>
                        <p className="font-medium">{row.name}</p>
                        <p className="text-xs text-muted-foreground">{row.email}</p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Badge variant="outline">{row.role}</Badge>
                        <Badge variant="outline">{row.track ?? "unassigned"}</Badge>
                        <Badge variant={row.active ? "default" : "secondary"}>
                          {row.active ? "active" : "inactive"}
                        </Badge>
                      </div>
                    </div>
                  ))}
                  {rows.length > 8 ? (
                    <p className="text-xs text-muted-foreground">
                      Showing the first 8 rows only.
                    </p>
                  ) : null}
                </div>
              ) : (
                <p className="text-muted-foreground">
                  No rows parsed yet.
                </p>
              )}
            </div>
          </div>
        </div>

        <SheetFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleImport} loading={isPending}>
            Import Users
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
