// Group detail drawer for viewing/editing group composition

import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
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
import type { Group, Track } from "@/type/group";
import { Label } from "@/components/ui/label";
import { UserIcon, UsersIcon, UserXIcon } from "lucide-react";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AxiosError } from "axios";
import { cn } from "@/lib/utils";
import {
  useQueryMentorList,
  useMutationReplaceMentor,
  useMutationConfirmMentorAssignments,
  useMutationUnassignMentors,
} from "@/query/mentorMatch";

const UNASSIGN_VALUE = "__unassign__";

function getTrackColor(track: Track) {
  switch (track.toLowerCase()) {
    case "frontend":
      return "bg-blue-100 text-blue-800";
    case "backend":
      return "bg-green-100 text-green-800";
    case "fullstack":
      return "bg-purple-100 text-purple-800";
    case "data":
      return "bg-orange-100 text-orange-800";
    default:
      return "bg-slate-100 text-slate-800";
  }
}

interface GroupDetailDrawerProps {
  group: Group | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function GroupDetailDrawer({
  group,
  open,
  onOpenChange,
}: GroupDetailDrawerProps) {
  const queryClient = useQueryClient();
  const [mentorDialogOpen, setMentorDialogOpen] = useState(false);
  const [selectedMentorId, setSelectedMentorId] = useState("");

  const { data: mentorListData } = useQueryMentorList();
  const mentors = mentorListData?.data ?? [];

  const replaceMentor = useMutationReplaceMentor();
  const assignMentor = useMutationConfirmMentorAssignments();
  const unassignMentor = useMutationUnassignMentors();

  const isReplacing = !!group?.mentor;
  const isPending = replaceMentor.isPending || assignMentor.isPending || unassignMentor.isPending;

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

  if (!group) return null;

  return (
    <>
      <Drawer open={open} onOpenChange={onOpenChange} direction="right">
        <DrawerContent className="h-full w-full overflow-hidden sm:max-w-lg">
          <DrawerHeader className="shrink-0">
            <DrawerTitle className="flex items-center gap-2">
              <UsersIcon className="size-5" />
              {group.name}
            </DrawerTitle>
            <DrawerDescription>
              View group details and composition
            </DrawerDescription>
          </DrawerHeader>

          <div className="min-h-0 flex-1 space-y-6 overflow-y-auto p-4">
            {/* Group Info */}
            <div className="space-y-4">
              <div>
                <Label className="text-muted-foreground">Track</Label>
                <Badge className={getTrackColor(group.track)}>
                  {group.track}
                </Badge>
              </div>
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
                    <div>
                      <p className="font-medium">{member.name}</p>
                      <p className="text-sm text-muted-foreground">
                        {member.email}
                      </p>
                    </div>
                    <Badge variant="outline">{member.role}</Badge>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </DrawerContent>
      </Drawer>

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
                      <Badge variant="outline" className="text-xs">{m.trackCode}</Badge>
                      <span className={cn(
                        "text-xs",
                        m.remainingCapacity === 0 ? "text-destructive" : "text-muted-foreground",
                      )}>
                        {m.currentAcceptedCount}/{m.maxGroupCount} groups
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
