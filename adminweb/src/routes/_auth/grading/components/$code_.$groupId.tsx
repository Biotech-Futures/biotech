import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useMemo } from "react";
import { Button } from "@/components/ui/button";
import { RubricForm } from "@/components/grading/RubricForm";
import { SubmissionPreview } from "@/components/grading/SubmissionPreview";
import {
  useQueryComponentRows,
  useQueryGroupMarking,
  useSaveGradesBulk,
} from "@/query/grading";
import { ChevronLeftIcon, ChevronRightIcon } from "lucide-react";

export const Route = createFileRoute("/_auth/grading/components/$code_/$groupId")({
  component: ComponentMarkingDetailPage,
});

function ComponentMarkingDetailPage() {
  const { code, groupId } = Route.useParams();
  const gid = Number(groupId);
  const navigate = useNavigate();

  // Full group marking payload — pick the block for this component. Same query
  // key as the per-group page, so the cache is shared.
  const groupQ = useQueryGroupMarking(gid);
  // Row list drives prev/next; if the user landed here directly this triggers
  // the fetch, but usually the cache is warm from the table view.
  const rowsQ = useQueryComponentRows(code);
  const save = useSaveGradesBulk();

  const block = useMemo(
    () => groupQ.data?.components.find((b) => b.component.code === code) ?? null,
    [groupQ.data, code],
  );

  const { prevId, nextId } = useMemo(() => {
    const rows = rowsQ.data?.rows ?? [];
    const idx = rows.findIndex((r) => r.group_id === gid);
    if (idx < 0) return { prevId: null, nextId: null };
    // Skip rows that don't have a submission — no point navigating to them.
    const back = rows.slice(0, idx).reverse().find((r) => r.submission_id != null);
    const fwd = rows.slice(idx + 1).find((r) => r.submission_id != null);
    return { prevId: back?.group_id ?? null, nextId: fwd?.group_id ?? null };
  }, [rowsQ.data, gid]);

  if (groupQ.isPending) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }
  if (groupQ.isError || !groupQ.data) {
    return <p className="text-destructive">Failed to load group {gid}.</p>;
  }
  if (!block) {
    return (
      <div className="space-y-2">
        <p className="text-destructive">No such component "{code}" for this group.</p>
        <Button asChild variant="outline">
          <Link to="/grading/components/$code" params={{ code }}>Back to list</Link>
        </Button>
      </div>
    );
  }

  const groupName = groupQ.data.group.group_name;

  const goto = (id: number | null) => {
    if (id == null) return;
    void navigate({
      to: "/grading/components/$code/$groupId",
      params: { code, groupId: String(id) },
    });
  };

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between">
        <h2 className="text-xl font-semibold">
          {block.component.name}: {groupName}
          <span className="text-muted-foreground text-sm"> #{gid}</span>
        </h2>
        <div className="flex gap-1">
          <Button
            variant="outline"
            size="sm"
            disabled={prevId == null}
            onClick={() => goto(prevId)}
          >
            <ChevronLeftIcon className="size-4" /> Prev
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={nextId == null}
            onClick={() => goto(nextId)}
          >
            Next <ChevronRightIcon className="size-4" />
          </Button>
          <Button asChild variant="ghost" size="sm">
            <Link to="/grading/components/$code" params={{ code }}>List</Link>
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <SubmissionPreview submission={block.submission} component={block.component} />
        <RubricForm
          submission={block.submission}
          criteria={block.criteria}
          grades={block.grades}
          isSaving={save.isPending}
          onSave={(items) => save.mutate({ groupId: gid, items })}
        />
      </div>
    </div>
  );
}
