import { useMemo } from "react";
import { ExternalLinkIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { SubmissionComponent, Submission } from "@/type/grading";

interface Props {
  submission: Submission | null;
  component: SubmissionComponent;
}

// Left-hand pane on both the per-group and per-component marking pages. PDF
// files render via the browser's native <iframe> viewer; text (SAQ) drops into
// a <pre>; a prototype link renders as an anchor. Missing submissions produce
// a dashed-border empty state.
export function SubmissionPreview({ submission, component }: Props) {
  const previewSrc = useMemo(() => submission?.file_url ?? null, [submission?.file_url]);

  if (!submission) {
    return (
      <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">
        No submission uploaded yet for {component.name}.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Submitted {new Date(submission.submitted_at).toLocaleString()}
          {submission.is_late ? " (late)" : ""}
        </p>
        {submission.file_url ? (
          <Button asChild variant="outline" size="sm">
            <a href={submission.file_url} target="_blank" rel="noreferrer">
              Open <ExternalLinkIcon className="ml-1 size-3" />
            </a>
          </Button>
        ) : null}
      </div>
      {submission.text ? (
        <pre className="rounded-md border bg-muted p-3 text-sm whitespace-pre-wrap max-h-[60vh] overflow-auto">
          {submission.text}
        </pre>
      ) : null}
      {submission.link ? (
        <a
          href={submission.link}
          className="text-sm text-primary underline"
          target="_blank"
          rel="noreferrer"
        >
          {submission.link}
        </a>
      ) : null}
      {previewSrc ? (
        <iframe
          src={previewSrc}
          title={`${component.name} preview`}
          className="w-full h-[60vh] rounded-md border"
        />
      ) : null}
    </div>
  );
}
