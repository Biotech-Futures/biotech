import {
  useMutationConfirmAssignments,
  useQueryMatchInfo,
} from "@/query/match";
import { MatchingBoard } from "@/components/match/MatchingBoard";
import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef } from "react";

export const Route = createFileRoute("/_auth/groups/student-matching")({
  validateSearch: (search) => ({
    run: search.run === true || search.run === "true",
  }),
  component: RouteComponent,
});

function RouteComponent() {
  const { run } = Route.useSearch();
  const hasAutoRun = useRef(false);
  const {
    data: matchInfoData,
    isFetching: isMatching,
    refetch: runMatch,
  } = useQueryMatchInfo();
  const confirmAssignments = useMutationConfirmAssignments();
  const recommendations = matchInfoData?.data.recommendations ?? [];
  const unmatchedStudents = matchInfoData?.data.unmatchedStudents ?? [];
  const notFullGroups = matchInfoData?.data.notFullGroups ?? [];

  useEffect(() => {
    if (!run || hasAutoRun.current) return;

    hasAutoRun.current = true;
    void runMatch();
  }, [run, runMatch]);

  async function onConfirmAssignments(
    assignments: Array<{ studentId: number; groupId: number | string }>,
  ) {
    await confirmAssignments.mutateAsync({ assignments });
    await runMatch();
  }

  return (
    <div className="space-y-4">
      <MatchingBoard
        recommendations={recommendations}
        unmatchedStudents={unmatchedStudents}
        notFullGroups={notFullGroups}
        onRunMatch={() => {
          void runMatch();
        }}
        onConfirmAssignments={onConfirmAssignments}
        isRunning={isMatching}
        isConfirming={confirmAssignments.isPending}
      />
    </div>
  );
}
