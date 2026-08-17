import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type {
  Grade,
  GradeBulkItem,
  RubricCriterion,
  Submission,
} from "@/type/grading";

interface RubricFormProps {
  submission: Submission | null;
  criteria: RubricCriterion[];
  grades: Grade[];
  isSaving: boolean;
  onSave: (items: GradeBulkItem[]) => void;
}

type FormState = Record<number, { mark: string; comment: string }>;

// Preload form state from existing grades keyed by criterion_id, with empty
// defaults for un-graded criteria. Runs whenever the underlying grades change
// (e.g. after a save round-trip refetches the marking payload).
function buildInitial(criteria: RubricCriterion[], grades: Grade[]): FormState {
  const byCriterion = new Map<number, Grade>();
  for (const g of grades) byCriterion.set(g.criterion, g);
  const state: FormState = {};
  for (const c of criteria) {
    const g = byCriterion.get(c.id);
    state[c.id] = {
      mark: g?.mark ?? "",
      comment: g?.comment ?? "",
    };
  }
  return state;
}

export function RubricForm({
  submission,
  criteria,
  grades,
  isSaving,
  onSave,
}: RubricFormProps) {
  const initial = useMemo(() => buildInitial(criteria, grades), [criteria, grades]);
  const [state, setState] = useState<FormState>(initial);

  useEffect(() => {
    setState(initial);
  }, [initial]);

  if (!submission) {
    return (
      <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">
        No submission for this component yet. Marks can't be entered until the
        group uploads.
      </div>
    );
  }

  if (criteria.length === 0) {
    return (
      <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">
        No rubric defined for this component yet. Add criteria in the admin
        rubric editor, then reload.
      </div>
    );
  }

  const handleChange = (criterionId: number, patch: Partial<{ mark: string; comment: string }>) => {
    setState((prev) => ({
      ...prev,
      [criterionId]: { ...prev[criterionId], ...patch },
    }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const items: GradeBulkItem[] = criteria.map((c) => ({
      submission: submission.id,
      criterion: c.id,
      // Empty string -> null so the mark is stored as "not graded yet" rather
      // than 0. Numeric validation is loose here — DRF's DecimalField rejects
      // anything unparseable and the error surfaces in the mutation.
      mark: state[c.id]?.mark?.trim() ? state[c.id].mark : null,
      comment: state[c.id]?.comment ?? "",
    }));
    onSave(items);
  };

  return (
    <form className="space-y-4" onSubmit={handleSubmit}>
      <div className="space-y-3">
        {criteria.map((c) => (
          <div key={c.id} className="rounded-md border p-3 space-y-2">
            <div className="flex items-baseline justify-between">
              <div>
                <p className="font-medium">{c.name}</p>
                {c.description ? (
                  <p className="text-xs text-muted-foreground">{c.description}</p>
                ) : null}
              </div>
              <span className="text-xs text-muted-foreground">/ {c.max_mark}</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-[8rem_1fr] gap-2">
              <Input
                type="number"
                inputMode="decimal"
                step="0.01"
                min="0"
                max={c.max_mark}
                placeholder="Mark"
                value={state[c.id]?.mark ?? ""}
                onChange={(e) => handleChange(c.id, { mark: e.target.value })}
                className="[appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
              />
              <Textarea
                placeholder="Comment (optional)"
                value={state[c.id]?.comment ?? ""}
                onChange={(e) => handleChange(c.id, { comment: e.target.value })}
                rows={2}
              />
            </div>
          </div>
        ))}
      </div>
      <div className="flex justify-end">
        <Button type="submit" disabled={isSaving}>
          {isSaving ? "Saving…" : "Save marks"}
        </Button>
      </div>
    </form>
  );
}
