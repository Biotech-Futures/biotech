import {
  useMutationConfirmMentorAssignments,
  useQueryMentorList,
  useQueryMentorMatchInfo,
  useQueryUnmatchedGroups,
  type MatchMode,
} from "@/query/mentorMatch";
import { MentorMatchingBoard } from "@/components/match/MentorMatchingBoard";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import { AxiosError } from "axios";
import { useState } from "react";
import { AlertTriangleIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export const Route = createFileRoute("/_auth/groups/mentor-matching")({
  component: RouteComponent,
});

function RouteComponent() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<MatchMode>("balanced");
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [confirmedCount, setConfirmedCount] = useState(0);

  const {
    data: unmatchedGroupsData,
    isPending: isLoadingGroups,
    error: groupsError,
    refetch: refetchGroups,
  } = useQueryUnmatchedGroups();
  const {
    data: mentorListData,
    isPending: isLoadingMentors,
    error: mentorsError,
    refetch: refetchMentors,
  } = useQueryMentorList();
  const loadError = groupsError ?? mentorsError;
  const {
    data: matchInfoData,
    isFetching: isMatching,
    refetch: runMatch,
  } = useQueryMentorMatchInfo(mode);
  const confirmAssignments = useMutationConfirmMentorAssignments();
  const recommendations = matchInfoData?.data ?? [];

  async function onConfirmAssignments(
    assignments: Array<{ groupId: number; mentorUserId: number }>,
  ) {
    try {
      const res = await confirmAssignments.mutateAsync({ assignments });
      setConfirmedCount(res.data.confirmedCount);
      setConfirmDialogOpen(true);
      queryClient.removeQueries({ queryKey: ["mentorMatchInfo"] });
      await Promise.all([
        queryClient.refetchQueries({ queryKey: ["unmatchedGroups"] }),
        queryClient.refetchQueries({ queryKey: ["matchedGroups"] }),
        queryClient.refetchQueries({ queryKey: ["mentorList"] }),
        queryClient.refetchQueries({ queryKey: ["groups"] }),
      ]);
    } catch (error) {
      if (error instanceof AxiosError) {
        const msg =
          (error.response?.data as { msg?: string } | undefined)?.msg ??
          error.message;
        toast.error(`Confirm failed: ${msg}`);
      } else {
        toast.error("Confirm failed. Please try again.");
      }
    }
  }

  function goToGroups() {
    setConfirmDialogOpen(false);
    void navigate({ to: "/groups", search: { page: 1 } });
  }

  return (
    <div className="space-y-4">
      {isLoadingGroups || isLoadingMentors ? (
        <p className="text-sm text-muted-foreground">Loading...</p>
      ) : loadError ? (
        // Without this, a failed load renders an empty board that reads as "everything is matched"
        <div className="flex items-start gap-3 rounded-xl border border-destructive/50 bg-destructive/5 p-4 text-sm">
          <AlertTriangleIcon className="mt-0.5 size-4 shrink-0 text-destructive" />
          <div className="space-y-2">
            <p className="font-medium text-destructive">
              Could not load mentor matching data
            </p>
            <p className="text-muted-foreground">{loadError.message}</p>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                void refetchGroups();
                void refetchMentors();
              }}
            >
              Retry
            </Button>
          </div>
        </div>
      ) : (
        <MentorMatchingBoard
          recommendations={recommendations}
          unmatchedGroups={unmatchedGroupsData?.data ?? []}
          mentors={mentorListData?.data ?? []}
          mode={mode}
          onModeChange={setMode}
          onRunMatch={() => { void runMatch(); }}
          onConfirmAssignments={onConfirmAssignments}
          isRunning={isMatching}
          isConfirming={confirmAssignments.isPending}
        />
      )}

      <Dialog open={confirmDialogOpen} onOpenChange={setConfirmDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {confirmedCount} assignment{confirmedCount === 1 ? "" : "s"} confirmed
            </DialogTitle>
            <DialogDescription>
              Where would you like to go next?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex-col gap-2 sm:flex-col">
            <Button className="w-full" onClick={goToGroups}>
              Go to Groups
            </Button>
            <Button className="w-full" variant="ghost" onClick={() => setConfirmDialogOpen(false)}>
              Decide Later
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
