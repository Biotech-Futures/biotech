import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { StudentFilters } from "@/components/user/StudentFilters";
import { StudentTable } from "@/components/user/StudentTable";
import { studentColumns } from "@/components/user/columns";
import { useQueryStudents } from "@/query/student";
import type { StudentTrack } from "@/type/user";

export const Route = createFileRoute("/_auth/student")({
  component: RouteComponent,
});

function RouteComponent() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [age, setAge] = useState("");
  const [track, setTrack] = useState<StudentTrack | undefined>();
  const [interest, setInterest] = useState("");
  const [inGroup, setInGroup] = useState<"yes" | "no" | "all">("all");
  const [page, setPage] = useState(1);

  const { data, isPending } = useQueryStudents({
    page,
    limit: 10,
    search: search || undefined,
    age: age ? Number(age) : undefined,
    track,
    interest: interest || undefined,
    inGroup: inGroup === "all" ? undefined : inGroup,
  });

  useEffect(() => {
    setPage(1);
  }, [search, age, track, interest, inGroup]);

  const students = data?.data.items ?? [];
  const total = data?.data.total ?? 0;
  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / 10)), [total]);

  const handleStudentClick = (student: { groupId: string | null }) => {
    if (!student.groupId) return;

    navigate({
      to: "/group",
      search: { groupId: student.groupId },
    });
  };

  return (
    <div className="p-4 space-y-4">
      <StudentFilters
        search={search}
        onSearchChange={setSearch}
        age={age}
        onAgeChange={setAge}
        track={track}
        onTrackChange={setTrack}
        interest={interest}
        onInterestChange={setInterest}
        inGroup={inGroup}
        onInGroupChange={setInGroup}
      />

      <StudentTable
        columns={studentColumns}
        data={students}
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
        onRowClick={handleStudentClick}
        isPending={isPending}
      />
    </div>
  );
}
