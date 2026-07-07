import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { StudentFilters } from "@/components/user/StudentFilters";
import { StudentTable } from "@/components/user/StudentTable";
import { studentColumns } from "@/components/user/columns";
import { Button } from "@/components/ui/button";
import {
  useQueryStudents,
  useQueryStates,
  useQueryHasUngroupedStudents,
} from "@/query/student";
import type { StudentUser } from "@/type/user";
import { ShuffleIcon } from "lucide-react";
import type { ColumnDef, SortingState } from "@tanstack/react-table";
import ManualAssignDialog from "@/components/student/ManualAssignDialog";

export const Route = createFileRoute("/_auth/student")({
  component: StudentPage,
});

function StudentPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [state, setState] = useState<string | undefined>();
  const [inGroup, setInGroup] = useState<"yes" | "no" | "all">("all");
  const [page, setPage] = useState(1);
  const [sorting, setSorting] = useState<SortingState>([
    { id: "name", desc: false },
  ]);
  const [assigningStudent, setAssigningStudent] = useState<StudentUser | null>(
    null,
  );

  const { data, isPending } = useQueryStudents({
    page,
    limit: 10,
    search: search || undefined,
    state,
    inGroup: inGroup === "all" ? undefined : inGroup,
    sortBy:
      sorting[0]?.id === "school" ||
      sorting[0]?.id === "yearLevel" ||
      sorting[0]?.id === "state" ||
      sorting[0]?.id === "group"
        ? sorting[0].id
        : "name",
    sortOrder: sorting[0]?.desc ? "desc" : "asc",
  });

  const { data: statesData, isPending: isLoadingStates } = useQueryStates();
  const { data: ungroupedData } = useQueryHasUngroupedStudents();
  const hasUngrouped = ungroupedData?.data?.hasUngrouped ?? false;

  useEffect(() => {
    setPage(1);
  }, [search, state, inGroup]);

  const students = data?.data?.items ?? [];
  const total = data?.data?.total ?? 0;
  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / 10)), [total]);

  const columns = useMemo<ColumnDef<StudentUser>[]>(() => {
    const actionColumn: ColumnDef<StudentUser> = {
      id: "actions",
      header: "Action",
      enableSorting: false,
      cell: ({ row }) => {
        if (row.original.groupId) return null;
        return (
          <Button
            size="sm"
            variant="outline"
            onClick={(event: React.MouseEvent<HTMLButtonElement>) => {
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
      {hasUngrouped && (
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
        state={state}
        onStateChange={setState}
        states={statesData?.data ?? []}
        isLoadingStates={isLoadingStates}
        inGroup={inGroup}
        onInGroupChange={setInGroup}
      />

      <StudentTable
        columns={columns}
        data={students}
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
        sorting={sorting}
        onSortingChange={(nextSorting) => {
          setSorting(nextSorting);
          setPage(1);
        }}
        manualSorting
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
