import { useState } from "react";
import {
  useQueryUnmatchedGroups,
  useQueryMentorList,
  useMutationConfirmMentorAssignments,
} from "@/query/mentorMatch";
import type { UnmatchedGroup, MentorListItem } from "@/type/mentorMatch";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ChevronDownIcon, ChevronRightIcon, UserPlusIcon, CheckIcon } from "lucide-react";
import { toast } from "sonner";
import { AxiosError } from "axios";
import { useQueryClient } from "@tanstack/react-query";
import { cn } from "@/lib/utils";

// ─── Assign Mentor Dialog ────────────────────────────────────────────────────

function AssignMentorDialog({
  group,
  mentors,
  open,
  onOpenChange,
  onConfirm,
  isConfirming,
}: {
  group: UnmatchedGroup | null;
  mentors: MentorListItem[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (groupId: number, mentorUserId: number) => Promise<void>;
  isConfirming: boolean;
}) {
  const [selectedMentorId, setSelectedMentorId] = useState<number | null>(null);

  function handleOpenChange(val: boolean) {
    if (!val) setSelectedMentorId(null);
    onOpenChange(val);
  }

  async function handleConfirm() {
    if (!group || selectedMentorId === null) return;
    await onConfirm(group.groupId, selectedMentorId);
    setSelectedMentorId(null);
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Assign Mentor</DialogTitle>
          <DialogDescription>
            Select a mentor for{" "}
            <span className="font-medium text-foreground">{group?.groupName}</span>
            {group && (
              <span className="ml-1 text-xs">
                ({group.trackCode} · {group.studentCount} students)
              </span>
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="max-h-[420px] overflow-y-auto space-y-2 pr-1">
          {mentors.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-6">
              No mentors available.
            </p>
          )}
          {mentors.map((m) => {
            const isSelected = selectedMentorId === m.mentorId;
            const isFull = m.remainingCapacity <= 0;
            return (
              <button
                key={m.mentorId}
                disabled={isFull}
                onClick={() => setSelectedMentorId(m.mentorId)}
                className={cn(
                  "w-full rounded-lg border px-4 py-3 text-left transition-colors",
                  isFull
                    ? "opacity-50 cursor-not-allowed bg-muted/30"
                    : "hover:bg-muted/40 cursor-pointer",
                  isSelected && "border-primary bg-primary/5",
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 space-y-1">
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-sm">{m.name}</p>
                      {isSelected && (
                        <CheckIcon className="size-4 text-primary flex-shrink-0" />
                      )}
                    </div>
                    {m.institution && (
                      <p className="text-xs text-muted-foreground">{m.institution}</p>
                    )}
                    {m.interests.length > 0 && (
                      <div className="flex flex-wrap gap-1 pt-0.5">
                        {m.interests.map((i) => (
                          <Badge key={i} variant="outline" className="text-[10px] px-1.5 py-0">
                            {i}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="flex-shrink-0 flex flex-col items-end gap-1">
                    <Badge variant="secondary" className="text-xs">{m.trackCode}</Badge>
                    <span className={cn(
                      "text-xs",
                      isFull ? "text-destructive" : "text-muted-foreground",
                    )}>
                      {isFull ? "Full" : `${m.remainingCapacity}/${m.maxGroupCount} slots`}
                    </span>
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            Cancel
          </Button>
          <Button
            disabled={selectedMentorId === null || isConfirming}
            onClick={() => void handleConfirm()}
          >
            {isConfirming ? "Assigning..." : "Confirm Assignment"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─── UnmatchedGroupsPanel ────────────────────────────────────────────────────

export function UnmatchedGroupsPanel() {
  const queryClient = useQueryClient();
  const { data, isPending, refetch } = useQueryUnmatchedGroups();
  const { data: mentorListData } = useQueryMentorList();
  const confirmAssignment = useMutationConfirmMentorAssignments();

  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
  const [assigningGroup, setAssigningGroup] = useState<UnmatchedGroup | null>(null);

  const groups = data?.data ?? [];
  const mentors = mentorListData?.data ?? [];

  function toggleExpand(id: number) {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleConfirmAssign(groupId: number, mentorUserId: number) {
    try {
      await confirmAssignment.mutateAsync({
        assignments: [{ groupId, mentorUserId }],
      });
      toast.success("Mentor assigned successfully.");
      setAssigningGroup(null);
      await refetch();
      await queryClient.invalidateQueries({ queryKey: ["matchedGroups"] });
    } catch (error) {
      if (error instanceof AxiosError) {
        const msg =
          (error.response?.data as { msg?: string } | undefined)?.msg ??
          error.message;
        toast.error(`Assignment failed: ${msg}`);
      } else {
        toast.error("Assignment failed. Please try again.");
      }
    }
  }

  if (isPending) {
    return <p className="text-sm text-muted-foreground">Loading unmatched groups...</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <h2 className="text-base font-semibold">Unmatched Groups</h2>
        <Badge variant="secondary">{groups.length}</Badge>
      </div>

      {groups.length === 0 ? (
        <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
          All groups have a mentor assigned.
        </div>
      ) : (
        <div className="rounded-xl border bg-card divide-y">
          {groups.map((g) => {
            const isExpanded = expandedIds.has(g.groupId);
            return (
              <div key={g.groupId}>
                <div className="flex items-center justify-between px-4 py-3 hover:bg-muted/40 transition-colors">
                  <button
                    className="flex items-center gap-2 min-w-0 flex-1 text-left"
                    onClick={() => toggleExpand(g.groupId)}
                  >
                    {isExpanded ? (
                      <ChevronDownIcon className="size-4 text-muted-foreground flex-shrink-0" />
                    ) : (
                      <ChevronRightIcon className="size-4 text-muted-foreground flex-shrink-0" />
                    )}
                    <span className="font-medium truncate">{g.groupName}</span>
                  </button>
                  <div className="flex items-center gap-2 flex-shrink-0 ml-2">
                    <Badge variant="outline" className="text-xs">{g.trackCode}</Badge>
                    <span className="text-xs text-muted-foreground">{g.studentCount} students</span>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 gap-1 text-xs"
                      onClick={() => setAssigningGroup(g)}
                    >
                      <UserPlusIcon className="size-3" />
                      Assign
                    </Button>
                  </div>
                </div>

                {isExpanded && (
                  <div className="px-4 pb-4 pt-2 bg-muted/10 space-y-3 border-t">
                    {g.students && g.students.length > 0 ? (
                      <div className="space-y-2">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                          Students
                        </p>
                        <div className="space-y-1.5">
                          {g.students.map((s) => (
                            <div key={s.name} className="rounded border bg-background px-3 py-2">
                              <p className="text-sm font-medium">{s.name}</p>
                              {s.interests.length > 0 && (
                                <div className="mt-1 flex flex-wrap gap-1">
                                  {s.interests.map((i) => (
                                    <Badge key={i} variant="outline" className="text-[10px] px-1.5 py-0">
                                      {i}
                                    </Badge>
                                  ))}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-1">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                          Student Interests
                        </p>
                        <div className="flex flex-wrap gap-1">
                          {[...new Set(g.studentInterests)].map((i) => (
                            <Badge key={i} variant="outline" className="text-xs">
                              {i}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <AssignMentorDialog
        group={assigningGroup}
        mentors={mentors}
        open={assigningGroup !== null}
        onOpenChange={(open) => { if (!open) setAssigningGroup(null); }}
        onConfirm={handleConfirmAssign}
        isConfirming={confirmAssignment.isPending}
      />
    </div>
  );
}
