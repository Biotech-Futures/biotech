import {
  useMutationConfirmMentorAssignments,
  useQueryMentorMatchInfo,
  useQueryUnmatchedGroups,
  type MatchMode,
} from "@/query/mentorMatch";
import { MentorMatchingBoard } from "@/components/match/MentorMatchingBoard";
import { createFileRoute } from "@tanstack/react-router";
import { toast } from "sonner";
import { AxiosError } from "axios";
import { useState } from "react";

export const Route = createFileRoute("/_auth/mentorMatching")({
  component: RouteComponent,
});

function RouteComponent() {
  const [mode, setMode] = useState<MatchMode>("balanced");

  const { data: unmatchedGroupsData, isPending: isLoadingGroups } =
    useQueryUnmatchedGroups();
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
      toast.success(
        `Confirmed ${res.data.confirmedCount} mentor assignment${res.data.confirmedCount === 1 ? "" : "s"}.`,
      );
      await runMatch();
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

  return (
    <div className="space-y-4 p-4">
      {isLoadingGroups ? (
        <p className="text-sm text-muted-foreground">Loading groups...</p>
      ) : (
        <MentorMatchingBoard
          recommendations={recommendations}
          unmatchedGroupCount={unmatchedGroupsData?.data.length ?? 0}
          mode={mode}
          onModeChange={setMode}
          onRunMatch={() => {
            void runMatch();
          }}
          onConfirmAssignments={onConfirmAssignments}
          isRunning={isMatching}
          isConfirming={confirmAssignments.isPending}
        />
      )}
    </div>
  );
}
