import { CsvImportSheet } from "@/components/user/CsvImportSheet";
import { parseStudentCsv } from "@/query/user";
import { useImportStudents } from "@/query/student";

interface StudentImportSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function StudentImportSheet({
  open,
  onOpenChange,
}: StudentImportSheetProps) {
  const importStudents = useImportStudents();
  return (
    <CsvImportSheet
      open={open}
      onOpenChange={onOpenChange}
      title="Import Students CSV"
      description="Upload the student registration export (Student email address, First Name, Surname, Guardian details, School Name, Year Level, Area(s) of Interest, Supervisor details, Parent/Guardian Approval ResponseID, Country, Region). Optional Group Number column: students sharing a number are placed in one group and skip auto-matching. Supervisors are created from the student rows; students with no approval ResponseID import inactive. Existing emails are skipped."
      noun="student"
      parse={parseStudentCsv}
      rowKey={(row) => row.email}
      rowPrimary={(row) => ({
        name: `${row.firstName} ${row.lastName}`.trim(),
        email: row.email,
        note: row.active
          ? undefined
          : "no approval yet — will import inactive",
      })}
      rowBadges={(row) => [
        row.state,
        `Yr ${row.yearLevel}`,
        `${row.interests.length} interests`,
        row.supervisorEmail ? "has supervisor" : "no supervisor",
        ...(row.groupNumber ? [`group ${row.groupNumber}`] : []),
      ]}
      onImport={async (rows) => {
        const res = await importStudents.mutateAsync(rows);
        return {
          created: res.data?.created?.length ?? 0,
          skipped: res.data?.skipped ?? [],
          coRegistration: res.data?.coRegistration,
        };
      }}
    />
  );
}
