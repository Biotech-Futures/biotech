import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { RubricForm } from "@/components/grading/RubricForm";
import { SubmissionPreview } from "@/components/grading/SubmissionPreview";
import {
  useDownloadGroupZip,
  useQueryGroupMarking,
  useSaveGradesBulk,
} from "@/query/grading";
import type { GroupMarkingComponentBlock } from "@/type/grading";
import { DownloadIcon, SearchIcon } from "lucide-react";
import { toast } from "sonner";

export const Route = createFileRoute("/_auth/grading/groups/$groupId")({
  component: GroupMarkingPage,
});

function GroupMarkingPage() {
  const { groupId } = Route.useParams();
  const gid = Number(groupId);
  const navigate = useNavigate();
  const query = useQueryGroupMarking(gid);
  const save = useSaveGradesBulk();
  const download = useDownloadGroupZip();

  const components = query.data?.components ?? [];
  const [activeCode, setActiveCode] = useState<string | undefined>(undefined);
  const effectiveCode = activeCode ?? components[0]?.component.code;
  const activeBlock = components.find((b) => b.component.code === effectiveCode);
  const groupName = query.data?.group.group_name;
  const [jumpId, setJumpId] = useState("");

  if (query.isPending) {
    return <p className="text-sm text-muted-foreground">Loading marking payload…</p>;
  }

  if (query.isError || !query.data) {
    return (
      <div className="space-y-2">
        <p className="text-destructive">Failed to load marking payload for group {gid}.</p>
        <Button asChild variant="outline">
          <Link to="/grading">Back</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted-foreground">Enter the group's ID.</p>
      <form
        className="flex gap-2 max-w-xl mb-10"
        onSubmit={(e) => {
          e.preventDefault();
          const n = Number(jumpId);
          if (!Number.isFinite(n) || n <= 0 || n === gid) return;
          setJumpId("");
          void navigate({
            to: "/grading/groups/$groupId",
            params: { groupId: String(n) },
          });
        }}
      >
        <div className="relative flex-1">
          <SearchIcon className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-[calc(50%+2px)] size-4 text-muted-foreground" />
          <Input
            type="number"
            min={1}
            placeholder="Group ID"
            value={jumpId}
            onChange={(e) => setJumpId(e.target.value)}
            className="pl-8 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
          />
        </div>
        <Button type="submit">Open</Button>
      </form>

      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h2 className="text-xl font-semibold">
          {groupName} <span className="text-muted-foreground text-sm">#{gid}</span>
        </h2>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={download.isPending}
            onClick={() =>
              download.mutate(
                { groupId: gid },
                {
                  onError: (e: unknown) => toast.error(`Download failed: ${(e as Error).message}`),
                },
              )
            }
          >
            <DownloadIcon className="size-4" />
            {download.isPending ? "Preparing…" : "Download all"}
          </Button>
          <Button asChild variant="ghost" size="sm">
            <Link to="/grading">Back</Link>
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-1 border-b">
        {components.map((b) => (
          <button
            key={b.component.code}
            type="button"
            onClick={() => setActiveCode(b.component.code)}
            className={cn(
              "px-3 py-1.5 text-sm rounded-t-md border-b-2 -mb-px transition-colors",
              b.component.code === effectiveCode
                ? "border-primary text-primary bg-primary/5"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {b.component.name}
          </button>
        ))}
      </div>

      {activeBlock ? (
        <ComponentPane
          block={activeBlock}
          isSaving={save.isPending}
          onSave={(items) => save.mutate({ groupId: gid, items })}
        />
      ) : null}
    </div>
  );
}

interface ComponentPaneProps {
  block: GroupMarkingComponentBlock;
  isSaving: boolean;
  onSave: (items: import("@/type/grading").GradeBulkItem[]) => void;
}

function ComponentPane({ block, isSaving, onSave }: ComponentPaneProps) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <SubmissionPreview submission={block.submission} component={block.component} />
      <div>
        <RubricForm
          submission={block.submission}
          criteria={block.criteria}
          grades={block.grades}
          isSaving={isSaving}
          onSave={onSave}
        />
      </div>
    </div>
  );
}
