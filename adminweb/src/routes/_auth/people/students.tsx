import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import { StudentFilters } from "@/components/user/StudentFilters";
import { StudentTable } from "@/components/user/StudentTable";
import { studentColumns } from "@/components/user/columns";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { useBulkDeleteUsers, type BulkStatusFilters } from "@/query/user";
import { useRemoveGroupMember } from "@/query/group";
import type { StudentUser } from "@/type/user";
import { ShuffleIcon, UserMinusIcon } from "lucide-react";
import type { ColumnDef, SortingState } from "@tanstack/react-table";
import ManualAssignDialog from "@/components/student/ManualAssignDialog";
import StudentBatchAssignDialog from "@/components/student/StudentBatchAssignDialog";
import { StudentBulkActionsBar } from "@/components/student/StudentBulkActionsBar";
import { StudentImportSheet } from "@/components/user/StudentImportSheet";
import { UploadIcon } from "lucide-react";
import { toast } from "sonner";

const DEFAULT_PAGE_SIZE = 25;

export const Route = createFileRoute("/_auth/people/students")({
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
  // "Select all matching" mode targets every student matching the filters
  // (across pages) except excludedIds. It powers Delete only — Assign/Remove
  // need the loaded rows, so they're disabled while it's active.
  const [selectAllMatching, setSelectAllMatching] = useState(false);
  const [excludedIds, setExcludedIds] = useState<Set<number>>(new Set());
  const [deleteConfirmText, setDeleteConfirmText] = useState("");
  const [forceDelete, setForceDelete] = useState(false);
  const [batchAssignOpen, setBatchAssignOpen] = useState(false);
  const [removeConfirmOpen, setRemoveConfirmOpen] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);

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
  const bulkDeleteUsers = useBulkDeleteUsers();

  // Filters change the matching set, so drop the current selection with them.
  useEffect(() => {
    setPage(1);
    setSelected(new Map());
    setSelectAllMatching(false);
    setExcludedIds(new Set());
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

  const clearSelection = useCallback(() => {
    setSelected(new Map());
    setSelectAllMatching(false);
    setExcludedIds(new Set());
  }, []);

  // Filters shared by the list query and the "select all matching" delete.
  const currentFilters: BulkStatusFilters = {
    role: "student",
    search: search || undefined,
    state,
    inGroup: inGroup === "all" ? undefined : inGroup,
  };

  const effectiveSelectedCount = selectAllMatching
    ? Math.max(0, total - excludedIds.size)
    : selected.size;

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

  const isRowSelected = useCallback(
    (id: number) =>
      selectAllMatching ? !excludedIds.has(id) : selected.has(id),
    [selectAllMatching, excludedIds, selected],
  );

  const selectedOnPageCount = students.filter((s) =>
    isRowSelected(s.id),
  ).length;
  const headerState: boolean | "indeterminate" =
    students.length > 0 && selectedOnPageCount === students.length
      ? true
      : selectedOnPageCount > 0
        ? "indeterminate"
        : false;

  const toggleRow = useCallback(
    (student: StudentUser) => {
      if (selectAllMatching) {
        setExcludedIds((prev) => {
          const next = new Set(prev);
          if (next.has(student.id)) next.delete(student.id);
          else next.add(student.id);
          return next;
        });
        return;
      }
      setSelected((prev) => {
        const next = new Map(prev);
        if (next.has(student.id)) next.delete(student.id);
        else next.set(student.id, student);
        return next;
      });
    },
    [selectAllMatching],
  );

  const toggleAllOnPage = useCallback(() => {
    if (selectAllMatching) {
      setExcludedIds((prev) => {
        const next = new Set(prev);
        // If every row on this page is currently included, exclude them all.
        const allIncluded =
          students.length > 0 && students.every((s) => !next.has(s.id));
        if (allIncluded) students.forEach((s) => next.add(s.id));
        else students.forEach((s) => next.delete(s.id));
        return next;
      });
      return;
    }
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
  }, [students, selectAllMatching]);

  // Offer to expand a full-page selection to every matching student.
  const showExpandOffer =
    !selectAllMatching &&
    students.length > 0 &&
    selectedOnPageCount === students.length &&
    total > students.length;

  const enterSelectAllMatching = useCallback(() => {
    setSelected(new Map());
    setExcludedIds(new Set());
    setSelectAllMatching(true);
  }, []);

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

  const handleBulkDelete = async () => {
    if (!selectAllMatching && selected.size === 0) {
      setDeleteConfirmOpen(false);
      return;
    }
    try {
      const res = await bulkDeleteUsers.mutateAsync(
        selectAllMatching
          ? {
              selectAll: true,
              filters: currentFilters,
              excludeIds: [...excludedIds].map(String),
              expectedCount: effectiveSelectedCount,
              force: forceDelete,
            }
          : { ids: [...selected.keys()].map(String), force: forceDelete },
      );
      if (!res.data) {
        toast.error(res.msg || "Unable to delete students.");
        return;
      }
      toast.success(res.msg);
      clearSelection();
    } catch {
      toast.error("Unable to delete students right now.");
    } finally {
      setDeleteConfirmOpen(false);
    }
  };

  const handleMatchStudents = () => {
    navigate({
      to: "/groups/student-matching",
      search: { run: true },
    });
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-end gap-2">
        <Button variant="outline" onClick={() => setImportOpen(true)}>
          <UploadIcon className="size-4" />
          Import Students CSV
        </Button>
        {hasUngrouped && (
          <Button onClick={handleMatchStudents}>
            <ShuffleIcon className="size-4" />
            Match Student
          </Button>
        )}
      </div>

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

      {effectiveSelectedCount > 0 && (
        <StudentBulkActionsBar
          count={effectiveSelectedCount}
          groupedCount={groupedSelected.length}
          onAssign={() => setBatchAssignOpen(true)}
          onRemove={() => setRemoveConfirmOpen(true)}
          onDelete={() => {
            setDeleteConfirmText("");
            setForceDelete(false);
            setDeleteConfirmOpen(true);
          }}
          onClear={clearSelection}
          isPending={isRemoving || bulkDeleteUsers.isPending}
          disableGroupActions={selectAllMatching}
        />
      )}

      {(showExpandOffer || selectAllMatching) && !isPending && (
        <div className="rounded-md border border-primary/20 bg-primary/10 px-3 py-2 text-center text-sm">
          {selectAllMatching ? (
            <span className="inline-flex flex-wrap items-center justify-center gap-2">
              <span aria-live="polite" className="font-medium">
                {excludedIds.size > 0
                  ? `${effectiveSelectedCount} of ${total} students selected.`
                  : `All ${total} students matching these filters are selected.`}
              </span>
              <Button
                variant="link"
                size="sm"
                className="h-auto p-0 font-semibold underline"
                onClick={clearSelection}
              >
                Clear selection
              </Button>
            </span>
          ) : (
            <span className="inline-flex flex-wrap items-center justify-center gap-2">
              <span className="font-medium">
                All {students.length} students on this page are selected.
              </span>
              <Button
                variant="link"
                size="sm"
                className="h-auto p-0 font-semibold underline"
                onClick={enterSelectAllMatching}
              >
                Select all {total} students matching these filters
              </Button>
            </span>
          )}
        </div>
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
          isSelected: isRowSelected,
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

      <AlertDialog
        open={deleteConfirmOpen}
        onOpenChange={(open) => {
          setDeleteConfirmOpen(open);
          if (!open) {
            setDeleteConfirmText("");
            setForceDelete(false);
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Delete {effectiveSelectedCount}{" "}
              {effectiveSelectedCount === 1 ? "student" : "students"}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              This permanently removes the selected{" "}
              {effectiveSelectedCount === 1 ? "account" : "accounts"} and all
              related data. This cannot be undone.
              {selectAllMatching ? (
                <> Every student matching the current filters will be deleted.</>
              ) : null}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="space-y-3">
            <label
              htmlFor="student-bulk-delete-force"
              className="flex items-start gap-2 text-sm"
            >
              <input
                id="student-bulk-delete-force"
                type="checkbox"
                className="mt-0.5 size-4"
                checked={forceDelete}
                onChange={(event) => setForceDelete(event.target.checked)}
              />
              <span>
                Force delete — also permanently delete each student's chat
                messages, uploaded resources, and other activity. Required to
                remove accounts that have any activity.
              </span>
            </label>
            {forceDelete ? (
              <p className="text-sm font-medium text-destructive">
                This destroys their content for everyone, not just the account,
                and cannot be undone.
              </p>
            ) : null}
            {selectAllMatching || forceDelete ? (
              <div className="space-y-1.5">
                <Label htmlFor="student-bulk-delete-confirm">
                  Type <span className="font-semibold">DELETE</span> to confirm
                </Label>
                <Input
                  id="student-bulk-delete-confirm"
                  autoComplete="off"
                  value={deleteConfirmText}
                  onChange={(event) => setDeleteConfirmText(event.target.value)}
                  placeholder="DELETE"
                />
              </div>
            ) : null}
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={bulkDeleteUsers.isPending}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={
                bulkDeleteUsers.isPending ||
                ((selectAllMatching || forceDelete) &&
                  deleteConfirmText !== "DELETE")
              }
              onClick={(event) => {
                event.preventDefault();
                void handleBulkDelete();
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <StudentImportSheet open={importOpen} onOpenChange={setImportOpen} />
    </div>
  );
}
