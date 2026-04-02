import {
  useMutationConfirmAssignments,
  useQueryIndividualStudents,
  useQueryMatchInfo,
} from "@/query/match";
import { MatchingBoard } from "@/components/match/MatchingBoard";
import { createFileRoute } from "@tanstack/react-router";
import { toast } from "sonner";
import { AxiosError } from "axios";

export const Route = createFileRoute("/_auth/matching")({
  component: RouteComponent,
});

function RouteComponent() {
  const { data: individualStudentsData, isPending } =
    useQueryIndividualStudents();
  const {
    data: matchInfoData,
    isFetching: isMatching,
    refetch: runMatch,
  } = useQueryMatchInfo();
  const confirmAssignments = useMutationConfirmAssignments();
  const recommendations = matchInfoData?.data ?? [];

  async function onConfirmAssignments(
    assignments: Array<{ studentId: number; groupId: number }>,
  ) {
    try {
      const res = await confirmAssignments.mutateAsync({ assignments });
      toast.success(
        `Confirmed ${res.data.assignedCount} student assignment${res.data.assignedCount === 1 ? "" : "s"}.`,
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
      {isPending ? (
        <p className="text-sm text-muted-foreground">Loading students...</p>
      ) : (
        <MatchingBoard
          recommendations={recommendations}
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
