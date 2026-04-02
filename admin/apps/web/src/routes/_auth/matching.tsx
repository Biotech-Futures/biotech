import { useQueryIndividualStudents } from "@/query/match";
import { IndividualStudentTable } from "@/components/match/IndividualStudentTable";
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/_auth/matching")({
  component: RouteComponent,
});

function RouteComponent() {
  const { data: individualStudentsData, isPending } =
    useQueryIndividualStudents();
  const students = individualStudentsData?.data ?? [];

  return (
    <div className="space-y-4 p-4">
      <div>
        <h1 className="text-xl font-semibold">Individual Students</h1>
        <p className="text-sm text-muted-foreground">
          Students who are currently not assigned to any active group.
        </p>
      </div>
      <IndividualStudentTable students={students} isLoading={isPending} />
    </div>
  );
}
