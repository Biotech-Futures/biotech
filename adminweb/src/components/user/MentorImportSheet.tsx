import { CsvImportSheet } from "@/components/user/CsvImportSheet";
import { parseMentorCsv } from "@/query/user";
import { useImportMentors } from "@/query/mentor";

interface MentorImportSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function MentorImportSheet({
  open,
  onOpenChange,
}: MentorImportSheetProps) {
  const importMentors = useImportMentors();
  return (
    <CsvImportSheet
      open={open}
      onOpenChange={onOpenChange}
      title="Import Mentors CSV"
      description="Upload the mentor registration export (Email Address, First Name, Surname, Country, Region, Mentor Reason, Capacity, Area(s) of Interest, Background, Institution or Company). Existing emails are skipped."
      noun="mentor"
      parse={parseMentorCsv}
      rowKey={(row) => row.email}
      rowPrimary={(row) => ({
        name: `${row.firstName} ${row.lastName}`.trim(),
        email: row.email,
        note: row.backgroundNote,
      })}
      rowBadges={(row) => [
        row.state ? `${row.country} · ${row.state}` : row.country,
        row.mentorBackground ?? "no background",
        `cap ${row.mentorMaxGroupCount}`,
        `${row.interests.length} interests`,
      ]}
      onImport={async (rows) => {
        const res = await importMentors.mutateAsync(rows);
        return {
          created: res.data?.created?.length ?? 0,
          skipped: res.data?.skipped ?? [],
        };
      }}
    />
  );
}
