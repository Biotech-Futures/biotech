import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import type { Group } from "@/type/group";
import { Label } from "@/components/ui/label";
import { UserIcon, UsersIcon, UserMinusIcon, UserXIcon } from "lucide-react";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AxiosError } from "axios";
import { cn } from "@/lib/utils";
import { useRemoveGroupMember } from "@/query/group";
import {
  useQueryMentorList,
  useMutationReplaceMentor,
  useMutationConfirmMentorAssignments,
  useMutationUnassignMentors,
} from "@/query/mentorMatch";

const UNASSIGN_VALUE = "__unassign__";

interface GroupDetailModalProps {
  group: Group | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onGroupChange?: (group: Group) => void;
}

export function GroupDetailModal({
  group,
  open,
  onOpenChange,
  onGroupChange,
}: GroupDetailModalProps) {
  const queryClient = useQueryClient();
  const [mentorDialogOpen, setMentorDialogOpen] = useState(false);
  const [selectedMentorId, setSelectedMentorId] = useState("");

  const { data: mentorListData } = useQueryMentorList();
  const mentors = mentorListData?.data ?? [];

  const replaceMentor = useMutationReplaceMentor();
  const assignMentor = useMutationConfirmMentorAssignments();
  const unassignMentor = useMutationUnassignMentors();
  const removeGroupMember = useRemoveGroupMember();

  const isReplacing = !!group?.mentor;
  const isPending =
    replaceMentor.isPending ||
    assignMentor.isPending ||
    unassignMentor.isPending ||
    removeGroupMember.isPending;

  function handleOpenDialog() {
    setSelectedMentorId("");
    setMentorDialogOpen(true);
  }

  async function handleConfirm() {
    if (!group || !selectedMentorId) return;

    try {
      if (selectedMentorId === UNASSIGN_VALUE) {
        await unassignMentor.mutateAsync([Number(group.id)]);
        toast.success("Mentor unassigned.");
      } else {
        const newMentorUserId = Number(selectedMentorId);
        if (isReplacing && group.mentor?.membershipId) {
          await replaceMentor.mutateAsync({
            membershipId: group.mentor.membershipId,
            groupId: Number(group.id),
            newMentorUserId,
          });
          toast.success("Mentor replaced.");
        } else {
          await assignMentor.mutateAsync({
            assignments: [{ groupId: Number(group.id), mentorUserId: newMentorUserId }],
          });
          toast.success("Mentor assigned.");
        }
      }

      setMentorDialogOpen(false);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["groups"] }),
        queryClient.invalidateQueries({ queryKey: ["group"] }),
        queryClient.invalidateQueries({ queryKey: ["matchedGroups"] }),
        queryClient.invalidateQueries({ queryKey: ["unmatchedGroups"] }),
      ]);
    } catch (error) {
      const msg =
        error instanceof AxiosError
          ? ((error.response?.data as { msg?: string } | undefined)?.msg ?? error.message)
          : "Operation failed. Please try again.";
      toast.error(msg);
    }
  }

  async function handleRemoveMember(member: Group["members"][number]) {
    if (!group) return;

    const confirmed = window.confirm(
      `Remove ${member.name || member.email} from ${group.name}?`,
    );
    if (!confirmed) return;

    try {
      const result = await removeGroupMember.mutateAsync({
        groupId: group.id,
        userId: member.id,
      });
      if (result.data) onGroupChange?.(result.data);
      toast.success("Student removed from group.");
    } catch (error) {
      const msg =
        error instanceof AxiosError
          ? ((error.response?.data as { msg?: string } | undefined)?.msg ??
            error.message)
          : "Could not remove student. Please try again.";
      toast.error(msg);
    }
  }

  if (!group) return null;

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="flex max-h-[92vh] flex-col overflow-hidden sm:max-w-2xl">
          <DialogHeader className="shrink-0">
            <DialogTitle className="flex items-center gap-2">
              <UsersIcon className="size-5" />
              {group.name}
            </DialogTitle>
            <DialogDescription>
              View group details and composition
            </DialogDescription>
          </DialogHeader>

          <div className="min-h-0 flex-1 space-y-6 overflow-y-auto p-4">
            {/* Group Info */}
            <div className="space-y-4">
              <div>
                <Label className="text-muted-foreground">Group Name</Label>
                <p className="font-medium">{group.name}</p>
              </div>
            </div>

            <Separator />

            {/* Mentor */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label className="flex items-center gap-1 text-muted-foreground">
                  <UserIcon className="size-4" />
                  Assigned Mentor
                </Label>
                <Button variant="outline" size="sm" className="h-7 text-xs" onClick={handleOpenDialog}>
                  {isReplacing ? "Replace Mentor" : "Assign Mentor"}
                </Button>
              </div>
              {group.mentor ? (
                <div className="p-3 rounded-md bg-muted/50">
                  <p className="font-medium">{group.mentor.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {group.mentor.email}
                  </p>
                </div>
              ) : (
                <div className="p-3 rounded-md bg-muted/50 text-muted-foreground">
                  No mentor assigned
                </div>
              )}
            </div>

            <Separator />

            {/* Members */}
            <div className="space-y-2">
              <Label className="flex items-center gap-1 text-muted-foreground">
                <UsersIcon className="size-4" />
                Group Members ({group.members.length})
              </Label>
              <div className="space-y-2">
                {group.members.map((member) => (
                  <div
                    key={member.id}
                    className="flex items-center justify-between p-3 rounded-md bg-muted/50"
                  >
                    <div className="min-w-0">
                      <p className="font-medium">{member.name}</p>
                      <p className="text-sm text-muted-foreground">
                        {member.email}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <Badge variant="outline">{member.role}</Badge>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="size-8 text-muted-foreground hover:text-destructive"
                        disabled={removeGroupMember.isPending}
                        aria-label={`Remove ${member.name || member.email} from group`}
                        title="Remove from group"
                        onClick={() => void handleRemoveMember(member)}
                      >
                        <UserMinusIcon className="size-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={mentorDialogOpen} onOpenChange={setMentorDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{isReplacing ? "Replace Mentor" : "Assign Mentor"}</DialogTitle>
            <DialogDescription>
              {isReplacing
                ? `Select a new mentor to replace ${group.mentor?.name}.`
                : "Select a mentor to assign to this group."}
            </DialogDescription>
          </DialogHeader>

          <div className="max-h-80 space-y-2 overflow-y-auto py-1 pr-1">
            {/* Unassign option — only shown when replacing */}
            {isReplacing && (
              <button
                type="button"
                onClick={() => setSelectedMentorId(UNASSIGN_VALUE)}
                className={cn(
                  "w-full rounded-lg border px-3 py-2 text-left text-sm transition-colors",
                  selectedMentorId === UNASSIGN_VALUE
                    ? "border-destructive bg-destructive/10"
                    : "border-dashed hover:bg-muted/50",
                )}
              >
                <span className="flex items-center gap-2 text-muted-foreground">
                  <UserXIcon className="size-4" />
                  Unassign (leave group unmatched)
                </span>
              </button>
            )}

            {mentors.map((m) => {
              const selected = selectedMentorId === String(m.mentorId);
              return (
                <button
                  key={m.mentorId}
                  type="button"
                  onClick={() => setSelectedMentorId(String(m.mentorId))}
                  className={cn(
                    "w-full rounded-lg border p-3 text-left text-sm transition-colors",
                    selected
                      ? "border-primary bg-primary/5"
                      : "hover:bg-muted/50",
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-medium">{m.name}</p>
                      {m.institution && (
                        <p className="text-xs text-muted-foreground">{m.institution}</p>
                      )}
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1">
                      <Badge variant="outline" className="text-xs">{m.countryName}</Badge>
                      <span className={cn(
                        "text-xs",
                        m.remainingCapacity === 0 ? "text-destructive" : "text-muted-foreground",
                      )}>
                        {m.currentAssignedCount}/{m.maxGroupCount} groups
                      </span>
                    </div>
                  </div>
                  {m.interests.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {m.interests.map((i) => (
                        <Badge key={i} variant="secondary" className="text-xs">
                          {i}
                        </Badge>
                      ))}
                    </div>
                  )}
                </button>
              );
            })}
          </div>

          <DialogFooter>
            <Button variant="ghost" onClick={() => setMentorDialogOpen(false)} disabled={isPending}>
              Cancel
            </Button>
            <Button onClick={handleConfirm} disabled={!selectedMentorId || isPending}>
              {isPending ? "Saving..." : "Confirm"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
