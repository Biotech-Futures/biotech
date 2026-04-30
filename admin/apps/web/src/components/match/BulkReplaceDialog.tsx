import { useState } from "react";
import { Button } from "@/components/ui/button";
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
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useNavigate } from "@tanstack/react-router";
import type { MatchedGroup, MentorListItem } from "@/type/mentorMatch";

const UNASSIGN_VALUE = "__unassign__";

type BulkReplaceDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  inactiveGroups: MatchedGroup[];
  mentors: MentorListItem[];
  onConfirm: (
    assignments: Array<{ groupId: number; mentorUserId: number }>,
    unassigns: number[],
  ) => Promise<void>;
  isPending: boolean;
};

export function BulkReplaceDialog({
  open,
  onOpenChange,
  inactiveGroups,
  mentors,
  onConfirm,
  isPending,
}: BulkReplaceDialogProps) {
  const navigate = useNavigate();
  const [selections, setSelections] = useState<Record<number, string>>({});

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) setSelections({});
    onOpenChange(nextOpen);
  }

  async function handleConfirm() {
    const assignments: Array<{ groupId: number; mentorUserId: number }> = [];
    const unassigns: number[] = [];

    for (const g of inactiveGroups) {
      const val = selections[g.groupId];
      if (!val) continue;
      if (val === UNASSIGN_VALUE) {
        unassigns.push(g.groupId);
      } else {
        assignments.push({ groupId: g.groupId, mentorUserId: Number(val) });
      }
    }

    await onConfirm(assignments, unassigns);
    setSelections({});
  }

  const actionCount = inactiveGroups.filter((g) => selections[g.groupId]).length;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Replace Inactive Mentors</DialogTitle>
          <DialogDescription>
            {inactiveGroups.length} group{inactiveGroups.length === 1 ? "" : "s"}{" "}
            {inactiveGroups.length === 1 ? "has" : "have"} an inactive mentor.
            Select a replacement for each group, or choose "Unassign" to leave the
            group unmatched.
          </DialogDescription>
        </DialogHeader>

        <div className="max-h-72 space-y-3 overflow-y-auto py-1">
          {inactiveGroups.map((g) => (
            <div
              key={g.groupId}
              className="flex items-center justify-between gap-3 rounded-lg border p-3"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{g.groupName}</p>
                <p className="text-xs text-muted-foreground">
                  Current:{" "}
                  <span className="text-destructive">
                    {g.mentor.name} (inactive)
                  </span>
                </p>
              </div>
              <Select
                value={selections[g.groupId] ?? ""}
                onValueChange={(val) =>
                  setSelections((prev) => ({ ...prev, [g.groupId]: val }))
                }
              >
                <SelectTrigger className="h-8 w-44 shrink-0 text-xs">
                  <SelectValue placeholder="Select action" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={UNASSIGN_VALUE} className="text-muted-foreground">
                    — Unassign (leave unmatched)
                  </SelectItem>
                  {mentors.map((m) => (
                    <SelectItem key={m.mentorId} value={String(m.mentorId)}>
                      {m.name}
                      {m.remainingCapacity === 0 && (
                        <span className="ml-1 text-muted-foreground">
                          (full)
                        </span>
                      )}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ))}
        </div>

        <DialogFooter className="flex-col gap-2 sm:flex-col">
          <Button
            className="w-full"
            onClick={handleConfirm}
            disabled={isPending || actionCount === 0}
          >
            {isPending
              ? "Confirming..."
              : `Confirm${actionCount > 0 ? ` (${actionCount})` : ""}`}
          </Button>
          <Button
            variant="outline"
            className="w-full"
            disabled={isPending}
            onClick={() => {
              onOpenChange(false);
              void navigate({ to: "/mentorMatching" });
            }}
          >
            Go to Mentor Matching
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
