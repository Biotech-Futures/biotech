import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { StudentFilters } from "@/components/user/StudentFilters";
import { StudentTable } from "@/components/user/StudentTable";
import { studentColumns } from "@/components/user/columns";
import { Button } from "@/components/ui/button";
import { useQueryStudents, useQueryTracks } from "@/query/student";
import type { StudentTrack, StudentUser } from "@/type/user";
import { ShuffleIcon } from "lucide-react";
import type { ColumnDef } from "@tanstack/react-table";
import ManualAssignDialog from "@/components/student/ManualAssignDialog";

export const Route = createFileRoute("/_auth/student")({
  component: StudentPage,
});

function StudentPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [yearLevel, setYearLevel] = useState("");
  const [track, setTrack] = useState<StudentTrack | undefined>();
  const [interest, setInterest] = useState("");
  const [inGroup, setInGroup] = useState<"yes" | "no" | "all">("all");
  const [page, setPage] = useState(1);
  const [assigningStudent, setAssigningStudent] = useState<StudentUser | null>(
    null,
  );

  const { data, isPending } = useQueryStudents({
    page,
    limit: 10,
    search: search || undefined,
    yearLevel: yearLevel ? Number(yearLevel) : undefined,
    track,
    interest: interest || undefined,
    inGroup: inGroup === "all" ? undefined : inGroup,
  });
  const { data: ungroupedStudentsData } = useQueryStudents({
    page: 1,
    limit: 1,
    inGroup: "no",
  });

  const { data: tracksData, isPending: isLoadingTracks } = useQueryTracks();

  useEffect(() => {
    setPage(1);
  }, [search, yearLevel, track, interest, inGroup]);

  const students = data?.data?.items ?? [];
  const total = data?.data?.total ?? 0;
  const hasUngroupedStudents = (ungroupedStudentsData?.data?.total ?? 0) > 0;
  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / 10)), [total]);

  const columns = useMemo<ColumnDef<StudentUser>[]>(() => {
    const actionColumn: ColumnDef<StudentUser> = {
      id: "actions",
      header: "Action",
      cell: ({ row }) => {
        if (row.original.groupId) return null;
        return (
          <Button
            size="sm"
            variant="outline"
            onClick={(event) => {
              event.stopPropagation();
              setAssigningStudent(row.original);
            }}
          >
            Assign to Group
          </Button>
        );
      },
    };

    return [...studentColumns, actionColumn];
  }, []);

  const handleMatchStudents = () => {
    navigate({
      to: "/matching",
      search: { run: true },
    });
  };

  return (
    <div className="p-4 space-y-4">
      {hasUngroupedStudents && (
        <div className="flex items-center justify-end">
          <Button onClick={handleMatchStudents}>
            <ShuffleIcon className="size-4" />
            Match Student
          </Button>
        </div>
      )}

      <StudentFilters
        search={search}
        onSearchChange={setSearch}
        yearLevel={yearLevel}
        onYearLevelChange={setYearLevel}
        track={track}
        onTrackChange={setTrack}
        tracks={tracksData?.data ?? []}
        isLoadingTracks={isLoadingTracks}
        interest={interest}
        onInterestChange={setInterest}
        inGroup={inGroup}
        onInGroupChange={setInGroup}
      />

      <StudentTable
        columns={columns}
        data={students}
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
        // onRowClick={handleStudentClick}
        isPending={isPending}
      />

      <ManualAssignDialog
        student={assigningStudent}
        open={Boolean(assigningStudent)}
        onOpenChange={(open) => {
          if (!open) {
            setAssigningStudent(null);
          }
        }}
      />
    </div>
  );
}
