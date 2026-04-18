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

export const Route = createFileRoute("/_auth/mentorMatching")({
  component: RouteComponent,
});

function RouteComponent() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<MatchMode>("balanced");
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [confirmedCount, setConfirmedCount] = useState(0);

  const { data: unmatchedGroupsData, isPending: isLoadingGroups } =
    useQueryUnmatchedGroups();
  const { data: mentorListData, isPending: isLoadingMentors } =
    useQueryMentorList();
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
      await Promise.all([
        runMatch(),
        queryClient.invalidateQueries({ queryKey: ["unmatchedGroups"] }),
        queryClient.invalidateQueries({ queryKey: ["matchedGroups"] }),
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
    void navigate({ to: "/group", search: { page: 1 } });
  }

  return (
    <div className="space-y-4 p-4">
      {isLoadingGroups || isLoadingMentors ? (
        <p className="text-sm text-muted-foreground">Loading...</p>
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
