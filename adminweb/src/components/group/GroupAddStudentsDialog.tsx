import { useMemo, useState } from "react";
import { useDebounce } from "use-debounce";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import { useQueryStudents } from "@/query/student";
import {
  useMutationConfirmAssignments,
  useQueryStudentSuggestions,
} from "@/query/match";
import type { StudentSuggestion } from "@/schema/match";
import { DEFAULT_GROUP_MAX_SIZE, studentCount } from "@/lib/group-capacity";
import type { Group } from "@/type/group";
import type { StudentUser } from "@/type/user";

interface GroupAddStudentsDialogProps {
  group: Group;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Called with the students that were just assigned, for optimistic UI. */
  onAdded: (students: StudentUser[]) => void;
}

/**
 * Capacity-aware picker for adding ungrouped students to a group — reuses the
 * same confirm-assignments mutation as the Students page and matching board, so
 * "add to group" now works directly from the Groups surface too.
 */
export function GroupAddStudentsDialog({
  group,
  open,
  onOpenChange,
  onAdded,
}: GroupAddStudentsDialogProps) {
  const [search, setSearch] = useState("");
  const [debouncedSearch] = useDebounce(search, 300);
  const [selected, setSelected] = useState<Map<number, StudentUser>>(new Map());
  const { mutate, isPending } = useMutationConfirmAssignments();

  const remaining = Math.max(0, DEFAULT_GROUP_MAX_SIZE - studentCount(group));

  const { data, isPending: isLoading } = useQueryStudents({
    page: 1,
    limit: 100,
    inGroup: "no",
    search: debouncedSearch || undefined,
  });
  const students = data?.data?.items ?? [];

  // Scored match suggestions for this group — annotate the full ungrouped list
  // so admins keep every candidate, but the best matches float to the top.
  const { data: suggestData, isLoading: isSuggestLoading } =
    useQueryStudentSuggestions(open ? Number(group.id) : null, open && remaining > 0);
  const suggestionByStudent = useMemo(() => {
    const map = new Map<number, StudentSuggestion>();
    for (const s of suggestData?.data.suggestions ?? []) {
      map.set(s.studentUserId, s);
    }
    return map;
  }, [suggestData]);
  const rankedStudents = useMemo(
    () =>
      students
        .map((student) => ({
          student,
          suggestion: suggestionByStudent.get(student.id),
        }))
        .sort((a, b) => {
          const sa = a.suggestion?.score ?? Number.NEGATIVE_INFINITY;
          const sb = b.suggestion?.score ?? Number.NEGATIVE_INFINITY;
          return sb - sa;
        }),
    [students, suggestionByStudent],
  );

  const selectedList = useMemo(() => [...selected.values()], [selected]);
  const overflow = Math.max(0, selectedList.length - remaining);

  function toggle(student: StudentUser) {
    setSelected((prev) => {
      const next = new Map(prev);
      if (next.has(student.id)) next.delete(student.id);
      else next.set(student.id, student);
      return next;
    });
  }

  function reset() {
    setSelected(new Map());
    setSearch("");
  }

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) reset();
    onOpenChange(nextOpen);
  }

  function handleConfirm() {
    if (!selectedList.length || overflow > 0) return;
    mutate(
      {
        assignments: selectedList.map((student) => ({
          studentId: student.id,
          groupId: Number(group.id),
        })),
      },
      {
        onSuccess: () => {
          onAdded(selectedList);
          reset();
          onOpenChange(false);
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add students to {group.name}</DialogTitle>
          <DialogDescription>
            {remaining > 0
              ? `${remaining} seat${remaining === 1 ? "" : "s"} left. Select ungrouped students to add.`
              : "This group is full."}
          </DialogDescription>
        </DialogHeader>

        <Input
          placeholder="Search ungrouped students..."
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />

        <div className="max-h-72 space-y-1 overflow-y-auto py-1 pr-1">
          {isLoading ? (
            <p className="p-3 text-sm text-muted-foreground">Loading...</p>
          ) : students.length === 0 ? (
            <p className="p-3 text-sm text-muted-foreground">
              No ungrouped students found.
            </p>
          ) : (
            <>
              {!isSuggestLoading && suggestionByStudent.size === 0 && (
                <p className="px-1 pb-1 text-xs text-muted-foreground">
                  No match recommendations — showing all students.
                </p>
              )}
              {rankedStudents.map(({ student, suggestion }, index) => {
                const checked = selected.has(student.id);
                const name =
                  `${student.firstName} ${student.lastName}`.trim() ||
                  student.email;
                const isTopMatch = index === 0 && suggestion !== undefined;
                return (
                  <button
                    key={student.id}
                    type="button"
                    aria-pressed={checked}
                    onClick={() => toggle(student)}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-md border px-3 py-2 text-left text-sm transition-colors",
                      checked
                        ? "border-primary bg-primary/5"
                        : "hover:bg-muted/50",
                    )}
                  >
                    <Checkbox
                      checked={checked}
                      className="pointer-events-none"
                      tabIndex={-1}
                      aria-hidden
                    />
                    <div className="min-w-0">
                      <p className="truncate font-medium">
                        {isTopMatch ? "★ " : ""}
                        {name}
                        {suggestion && (
                          <span className="ml-2 text-xs text-muted-foreground">
                            score {Math.round(suggestion.score)}
                          </span>
                        )}
                      </p>
                      <p className="truncate text-xs text-muted-foreground">
                        {suggestion && suggestion.sharedInterests.length
                          ? `Shared: ${suggestion.sharedInterests.slice(0, 3).join(", ")}`
                          : student.email}
                      </p>
                    </div>
                  </button>
                );
              })}
            </>
          )}
        </div>

        {overflow > 0 && (
          <p className="text-xs text-amber-700 dark:text-amber-400">
            Only {remaining} seat{remaining === 1 ? "" : "s"} left. Deselect{" "}
            {overflow} student{overflow === 1 ? "" : "s"}.
          </p>
        )}

        <DialogFooter>
          <Button
            variant="outline"
            disabled={isPending}
            onClick={() => handleOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={
              selectedList.length === 0 ||
              isPending ||
              overflow > 0 ||
              remaining === 0
            }
          >
            {isPending
              ? "Adding..."
              : `Add${selectedList.length ? ` (${selectedList.length})` : ""}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
