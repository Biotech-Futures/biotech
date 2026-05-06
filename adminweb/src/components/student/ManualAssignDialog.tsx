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
import { Button } from "../ui/button";
const DEFAULT_GROUP_MAX_SIZE = 5;

export default function ManualAssignDialog({
  student,
  open,
  onOpenChange,
}: {
  student: StudentUser | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [selectedGroupId, setSelectedGroupId] = useState("");
  const { mutate, isPending } = useMutationConfirmAssignments();
  const { data: groupsData } = useQueryGroups({
    page: 1,
    limit: 100,
    track: student?.track || undefined,
  });
  const groups = useMemo(() => {
    const groups = groupsData?.data?.items ?? [];

    return groups
      .map((group) => ({
        id: group.id,
        name: group.name,
        track: group.track,
        studentCount: group.members.filter(
          (member) => member.role === "student",
        ).length,
      }))
      .filter((group) => group.studentCount < DEFAULT_GROUP_MAX_SIZE)
      .sort((a, b) => {
        if (a.studentCount !== b.studentCount) {
          return a.studentCount - b.studentCount;
        }

        return a.name.localeCompare(b.name);
      });
  }, [groupsData?.data?.items]);

  async function handleConfirmAssignment(groupId: number) {
    if (!student) return;
    mutate({
      assignments: [{ studentId: student.id, groupId }],
    });
  }
  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) {
      setSelectedGroupId("");
    }

    onOpenChange(nextOpen);
  }

  async function handleConfirm() {
    if (!selectedGroupId) return;

    const groupId = Number(selectedGroupId);
    if (!student || !Number.isFinite(groupId) || groupId <= 0) return;
    await handleConfirmAssignment(groupId);
    setSelectedGroupId("");
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Assign Student to Group</DialogTitle>
          <DialogDescription>
            Select a group for{" "}
            <span className="font-medium text-foreground">
              {[student?.firstName, student?.lastName]
                .filter(Boolean)
                .join(" ")}
            </span>
            {student?.track ? (
              <span className="ml-1 text-xs">({student.track})</span>
            ) : null}
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
                      {group.name} · {group.track}{" "}
                    </SelectItem>
                  ))
                )}
              </SelectGroup>
            </SelectContent>
          </Select>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={() => void handleConfirm()}
            disabled={!selectedGroupId || isPending || groups.length === 0}
          >
            {isPending ? "Assigning..." : "Confirm Assignment"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
