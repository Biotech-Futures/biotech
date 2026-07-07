import { useQueryGroups } from "@/query/group";
import { useMutationConfirmAssignments } from "@/query/match";
import type { StudentUser } from "@/type/user";
import { useMemo, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";

const DEFAULT_GROUP_MAX_SIZE = 5;

export default function StudentBatchAssignDialog({
  students,
  open,
  onOpenChange,
  onAssigned,
}: {
  students: StudentUser[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAssigned?: () => void;
}) {
  const [selectedGroupId, setSelectedGroupId] = useState("");
  const { mutate, isPending } = useMutationConfirmAssignments();
  const { data: groupsData } = useQueryGroups({ page: 1, limit: 100 });

  const groups = useMemo(() => {
    const items = groupsData?.data?.items ?? [];
    return items
      .map((group) => {
        const studentCount = group.members.filter(
          (member) => member.role === "student",
        ).length;
        return {
          id: group.id,
          name: group.name,
          studentCount,
          remaining: Math.max(0, DEFAULT_GROUP_MAX_SIZE - studentCount),
        };
      })
      .filter((group) => group.remaining > 0)
      .sort((a, b) => {
        if (a.remaining !== b.remaining) return b.remaining - a.remaining;
        return a.name.localeCompare(b.name);
      });
  }, [groupsData?.data?.items]);

  const selectedGroup = groups.find(
    (group) => String(group.id) === selectedGroupId,
  );
  const overflow = selectedGroup
    ? Math.max(0, students.length - selectedGroup.remaining)
    : 0;

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) setSelectedGroupId("");
    onOpenChange(nextOpen);
  }

  function handleConfirm() {
    const groupId = Number(selectedGroupId);
    if (!students.length || !Number.isFinite(groupId) || groupId <= 0) return;

    mutate(
      {
        assignments: students.map((student) => ({
          studentId: student.id,
          groupId,
        })),
      },
      {
        onSuccess: () => {
          setSelectedGroupId("");
          onOpenChange(false);
          onAssigned?.();
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Assign students to a group</DialogTitle>
          <DialogDescription>
            Assigning{" "}
            <span className="font-medium text-foreground">
              {students.length}{" "}
              {students.length === 1 ? "student" : "students"}
            </span>{" "}
            to the selected group.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2">
          <Select value={selectedGroupId} onValueChange={setSelectedGroupId}>
            <SelectTrigger>
              <SelectValue placeholder="Select a group" />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                {!groups.length ? (
                  <SelectItem value="__empty" disabled>
                    No groups with available space
                  </SelectItem>
                ) : (
                  groups.map((group) => (
                    <SelectItem key={group.id} value={String(group.id)}>
                      {group.name} · {group.studentCount}/{DEFAULT_GROUP_MAX_SIZE}{" "}
                      ({group.remaining} left)
                    </SelectItem>
                  ))
                )}
              </SelectGroup>
            </SelectContent>
          </Select>
          {overflow > 0 && (
            <p className="text-xs text-amber-700 dark:text-amber-400">
              This group has only {selectedGroup?.remaining} seat
              {selectedGroup?.remaining === 1 ? "" : "s"} left. Deselect{" "}
              {overflow} student{overflow === 1 ? "" : "s"} or pick a group with
              more room.
            </p>
          )}
        </div>

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
              !selectedGroupId || isPending || groups.length === 0 || overflow > 0
            }
          >
            {isPending ? "Assigning..." : "Confirm assignment"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
