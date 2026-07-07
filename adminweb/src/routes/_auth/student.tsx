import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import { StudentFilters } from "@/components/user/StudentFilters";
import { StudentTable } from "@/components/user/StudentTable";
import { studentColumns } from "@/components/user/columns";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  useQueryStudents,
  useQueryStates,
  useQueryHasUngroupedStudents,
} from "@/query/student";
import { useRemoveGroupMember } from "@/query/group";
import type { StudentUser } from "@/type/user";
import { ShuffleIcon, UserMinusIcon } from "lucide-react";
import type { ColumnDef, SortingState } from "@tanstack/react-table";
import ManualAssignDialog from "@/components/student/ManualAssignDialog";
import StudentBatchAssignDialog from "@/components/student/StudentBatchAssignDialog";
import { StudentBulkActionsBar } from "@/components/student/StudentBulkActionsBar";
import { toast } from "sonner";

const DEFAULT_PAGE_SIZE = 25;

export const Route = createFileRoute("/_auth/student")({
  component: StudentPage,
});

function StudentPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [state, setState] = useState<string | undefined>();
  const [inGroup, setInGroup] = useState<"yes" | "no" | "all">("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [sorting, setSorting] = useState<SortingState>([
    { id: "name", desc: false },
  ]);
  const [assigningStudent, setAssigningStudent] = useState<StudentUser | null>(
    null,
  );
  // Selected students, keyed by id, so the selection persists across pages and
  // we keep each student's group info for the batch/remove actions.
  const [selected, setSelected] = useState<Map<number, StudentUser>>(new Map());
  const [batchAssignOpen, setBatchAssignOpen] = useState(false);
  const [removeConfirmOpen, setRemoveConfirmOpen] = useState(false);

  const { data, isPending } = useQueryStudents({
    page,
    limit: pageSize,
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
  const { mutateAsync: removeMemberAsync, isPending: isRemoving } =
    useRemoveGroupMember();

  // Filters change the matching set, so drop the current selection with them.
  useEffect(() => {
    setPage(1);
    setSelected(new Map());
  }, [search, state, inGroup]);

  const students = useMemo(
    () => data?.data?.items ?? [],
    [data?.data?.items],
  );
  const total = data?.data?.total ?? 0;

  // Keep selected snapshots in sync with refetched page data so group changes
  // (e.g. after a single assign) are reflected in the bulk-action counts.
  useEffect(() => {
    setSelected((prev) => {
      if (prev.size === 0) return prev;
      let changed = false;
      const next = new Map(prev);
      for (const student of students) {
        if (next.has(student.id) && next.get(student.id) !== student) {
          next.set(student.id, student);
          changed = true;
        }
      }
      return changed ? next : prev;
    });
  }, [students]);
  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(total / pageSize)),
    [total, pageSize],
  );

  const clearSelection = useCallback(() => setSelected(new Map()), []);

  const openAssign = useCallback(
    (student: StudentUser) => setAssigningStudent(student),
    [],
  );

  const handleUnassignOne = useCallback(
    async (student: StudentUser) => {
      if (!student.groupId) return;
      const label = `${student.firstName} ${student.lastName}`.trim();
      const confirmed = window.confirm(
        `Remove ${label} from ${student.groupName ?? "their group"}?`,
      );
      if (!confirmed) return;
      try {
        await removeMemberAsync({
          groupId: String(student.groupId),
          userId: String(student.id),
        });
        toast.success("Student removed from group.");
        setSelected((prev) => {
          const next = new Map(prev);
          next.delete(student.id);
          return next;
        });
      } catch {
        toast.error("Unable to remove the student from their group.");
      }
    },
    [removeMemberAsync],
  );

  const columns = useMemo<ColumnDef<StudentUser>[]>(() => {
    const actionColumn: ColumnDef<StudentUser> = {
      id: "actions",
      header: "Action",
      enableSorting: false,
      cell: ({ row }) => {
        const student = row.original;
        if (student.groupId) {
          return (
            <Button
              size="sm"
              variant="ghost"
              className="text-destructive hover:text-destructive"
              onClick={(event: React.MouseEvent<HTMLButtonElement>) => {
                event.stopPropagation();
                void handleUnassignOne(student);
              }}
            >
              <UserMinusIcon className="size-4" />
              Remove
            </Button>
          );
        }
        return (
          <Button
            size="sm"
            variant="outline"
            onClick={(event: React.MouseEvent<HTMLButtonElement>) => {
              event.stopPropagation();
              openAssign(student);
            }}
          >
            Assign to Group
          </Button>
        );
      },
    };

    return [...studentColumns, actionColumn];
  }, [handleUnassignOne, openAssign]);

  const selectedList = useMemo(() => [...selected.values()], [selected]);
  const groupedSelected = useMemo(
    () => selectedList.filter((student) => student.groupId),
    [selectedList],
  );

  const selectedOnPage = students.filter((student) => selected.has(student.id));
  const headerState: boolean | "indeterminate" =
    students.length > 0 && selectedOnPage.length === students.length
      ? true
      : selectedOnPage.length > 0
        ? "indeterminate"
        : false;

  const toggleRow = useCallback((student: StudentUser) => {
    setSelected((prev) => {
      const next = new Map(prev);
      if (next.has(student.id)) next.delete(student.id);
      else next.set(student.id, student);
      return next;
    });
  }, []);

  const toggleAllOnPage = useCallback(() => {
    setSelected((prev) => {
      const next = new Map(prev);
      const allSelected =
        students.length > 0 && students.every((s) => next.has(s.id));
      if (allSelected) {
        students.forEach((s) => next.delete(s.id));
      } else {
        students.forEach((s) => next.set(s.id, s));
      }
      return next;
    });
  }, [students]);

  const handlePageSizeChange = (size: number) => {
    setPageSize(size);
    setPage(1);
  };

  const handleBatchRemove = async () => {
    const targets = groupedSelected;
    if (!targets.length) {
      setRemoveConfirmOpen(false);
      return;
    }
    // Settle every removal independently so one failure doesn't strand the rest.
    const outcomes = await Promise.allSettled(
      targets.map((student) =>
        removeMemberAsync({
          groupId: String(student.groupId),
          userId: String(student.id),
        }).then(() => student.id),
      ),
    );
    const removedIds = outcomes
      .filter(
        (o): o is PromiseFulfilledResult<number> => o.status === "fulfilled",
      )
      .map((o) => o.value);
    const failed = targets.length - removedIds.length;

    if (removedIds.length) {
      // Drop only the students we actually removed; keep other selections.
      setSelected((prev) => {
        const next = new Map(prev);
        removedIds.forEach((id) => next.delete(id));
        return next;
      });
    }

    if (failed === 0) {
      toast.success(
        `Removed ${removedIds.length} student${removedIds.length === 1 ? "" : "s"} from ${removedIds.length === 1 ? "their group" : "their groups"}.`,
      );
    } else if (removedIds.length) {
      toast.error(
        `Removed ${removedIds.length}, but ${failed} could not be removed.`,
      );
    } else {
      toast.error("Unable to remove the selected students from their groups.");
    }
    setRemoveConfirmOpen(false);
  };

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

      {selected.size > 0 && (
        <StudentBulkActionsBar
          count={selected.size}
          groupedCount={groupedSelected.length}
          onAssign={() => setBatchAssignOpen(true)}
          onRemove={() => setRemoveConfirmOpen(true)}
          onClear={clearSelection}
          isPending={isRemoving}
        />
      )}

      <StudentTable
        columns={columns}
        data={students}
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
        pageSize={pageSize}
        onPageSizeChange={handlePageSizeChange}
        sorting={sorting}
        onSortingChange={(nextSorting) => {
          setSorting(nextSorting);
          setPage(1);
        }}
        manualSorting
        isPending={isPending}
        selection={{
          isSelected: (id) => selected.has(id),
          onToggleRow: toggleRow,
          headerState,
          onToggleAll: toggleAllOnPage,
        }}
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

      <StudentBatchAssignDialog
        students={selectedList}
        open={batchAssignOpen}
        onOpenChange={setBatchAssignOpen}
        onAssigned={clearSelection}
      />

      <AlertDialog
        open={removeConfirmOpen}
        onOpenChange={setRemoveConfirmOpen}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Remove {groupedSelected.length}{" "}
              {groupedSelected.length === 1 ? "student" : "students"} from{" "}
              {groupedSelected.length === 1 ? "their group" : "their groups"}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              They will become ungrouped and can be reassigned at any time.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isRemoving}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={isRemoving}
              onClick={(event) => {
                event.preventDefault();
                void handleBatchRemove();
              }}
            >
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
