import { useMemo, useState } from "react";
import { DownloadIcon } from "lucide-react";
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
import { parseCsvUsers } from "@/query/user";
import type { CsvUserRow } from "@/type/user";
import { toast } from "sonner";

interface UserBulkUploadSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onImport: (rows: CsvUserRow[]) => Promise<void> | void;
  isPending?: boolean;
}

const USER_IMPORT_TEMPLATE = [
  [
    "firstName",
    "lastName",
    "email",
    "role",
    "track",
    "adminTracks",
    "adminIsGlobal",
    "school",
    "yearLevel",
    "interests",
    "institution",
    "mentorReason",
    "maxGroupCount",
    "background",
    "supervisorEmail",
    "status",
  ],
  [
    "Ava",
    "Nguyen",
    "ava.nguyen@example.com",
    "student",
    "AUS-NSW",
    "",
    "",
    "Example High School",
    "10",
    "Biotechnology, Data Science",
    "",
    "",
    "",
    "",
    "mia.chen@example.com",
    "active",
  ],
  [
    "Noah",
    "Patel",
    "noah.patel@example.com",
    "mentor",
    "AUS-QLD",
    "",
    "",
    "",
    "",
    "Biotechnology, Research",
    "University of Sydney",
    "Interested in supporting student research projects",
    "2",
    "Research",
    "",
    "active",
  ],
  [
    "Mia",
    "Chen",
    "mia.chen@example.com",
    "supervisor",
    "AUS-VIC",
    "",
    "",
    "Example High School",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "active",
  ],
  [
    "Liam",
    "Taylor",
    "liam.taylor@example.com",
    "admin",
    "",
    "AUS-NSW|AUS-QLD",
    "no",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "active",
  ],
];

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
      toast.error(
        error instanceof Error ? error.message : "Failed to parse the CSV file.",
      );
    }
  };

  const handleImport = async () => {
    if (!rows.length) {
      toast.error("Please choose a valid CSV file first.");
      return;
    }
    const rowMissingSchool = rows.find(
      (row) =>
        (row.role === "student" && !row.schoolName.trim()) ||
        (row.role === "supervisor" && !row.supervisorSchoolName.trim()),
    );
    if (rowMissingSchool) {
      toast.error(
        `School is required for ${rowMissingSchool.role} user ${rowMissingSchool.email}.`,
      );
      return;
    }
    const adminMissingTracks = rows.find(
      (row) =>
        row.role === "admin" && !row.adminIsGlobal && !row.adminTracks.length,
    );
    if (adminMissingTracks) {
      toast.error(
        `Select global admin or at least one admin track for admin user ${adminMissingTracks.email}.`,
      );
      return;
    }
    const mentorMissingProfile = rows.find(
      (row) =>
        row.role === "mentor" &&
        (!row.mentorInstitution.trim() ||
          !row.mentorReason.trim() ||
          row.mentorMaxGroupCount === null ||
          row.mentorMaxGroupCount < 0),
    );
    if (mentorMissingProfile) {
      toast.error(
        `Institution, mentor reason, and max group count are required for mentor user ${mentorMissingProfile.email}.`,
      );
      return;
    }
    const studentMissingYearLevel = rows.find(
      (row) =>
        row.role === "student" &&
        (!row.yearLevel || row.yearLevel < 9 || row.yearLevel > 12),
    );
    if (studentMissingYearLevel) {
      toast.error(
        `Year level must be between 9 and 12 for student user ${studentMissingYearLevel.email}.`,
      );
      return;
    }
    const roleMissingInterests = rows.find(
      (row) =>
        (row.role === "student" || row.role === "mentor") &&
        !row.interests.length,
    );
    if (roleMissingInterests) {
      toast.error(
        `At least one interest is required for ${roleMissingInterests.role} user ${roleMissingInterests.email}.`,
      );
      return;
    }

    await onImport(rows);
    setFile(null);
    setRows([]);
  };

  const handleDownloadTemplate = () => {
    const csv = USER_IMPORT_TEMPLATE.map((row) =>
      row.map(formatCsvCell).join(","),
    ).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = "user-bulk-upload-template.csv";
    link.click();
    window.URL.revokeObjectURL(url);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[92vh] flex-col overflow-hidden sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Bulk Upload Users</DialogTitle>
          <DialogDescription>
            Upload a CSV with either a single name column or split firstName and
            lastName columns, plus email, role, track, adminTracks, adminIsGlobal, school,
            yearLevel, interests, institution, mentorReason, maxGroupCount,
            background, status, and supervisorEmail (student rows only —
            use the supervisor's email to link them; the supervisor must also be in
            this CSV or already exist in the system).
          </DialogDescription>
        </DialogHeader>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 pb-4">
          <div className="flex items-center justify-between gap-3 rounded-md border bg-muted/30 px-4 py-3">
            <div>
              <p className="text-sm font-medium">CSV template</p>
              <p className="text-xs text-muted-foreground">
                Start with the required columns and sample rows.
              </p>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleDownloadTemplate}
            >
              <DownloadIcon />
              Download
            </Button>
          </div>

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
                        <p className="font-medium">{`${row.firstName} ${row.lastName}`.trim()}</p>
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

        <DialogFooter className="shrink-0 border-t">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleImport} loading={isPending}>
            Import Users
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function formatCsvCell(value: string) {
  if (/[",\n]/.test(value)) {
    return `"${value.replaceAll('"', '""')}"`;
  }

  return value;
}
