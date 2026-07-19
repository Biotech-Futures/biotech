import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  useCreateGroup,
  useQueryNextGroupName,
  useUpdateGroup,
} from "@/query/group";
import type { Group } from "@/type/group";

type GroupNameDialogProps = {
  mode: "create" | "edit";
  /** The group being renamed. Required for mode="edit". */
  group?: Pick<Group, "id" | "name"> | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved?: (group: Group) => void;
};

function serverMessage(error: unknown): string | undefined {
  return (error as { response?: { data?: { msg?: string } } })?.response?.data
    ?.msg;
}

export function GroupNameDialog({
  mode,
  group,
  open,
  onOpenChange,
  onSaved,
}: GroupNameDialogProps) {
  const isEdit = mode === "edit";
  const [name, setName] = useState("");
  /** Last suggestion received; the input holds it unless the admin typed over it. */
  const [prefill, setPrefill] = useState("");
  const [error, setError] = useState<string | null>(null);

  const createGroup = useCreateGroup();
  const updateGroup = useUpdateGroup();
  const nextName = useQueryNextGroupName(open && !isEdit);
  const isPending = isEdit ? updateGroup.isPending : createGroup.isPending;

  // A cached preview from an earlier open may already be superseded, so it counts
  // only once this open's fetch has settled successfully — while it is in flight,
  // or if it failed (react-query keeps the last good data), the field stays empty.
  const suggestedName =
    nextName.isSuccess && !nextName.isFetching
      ? nextName.data.data.name
      : "";

  useEffect(() => {
    if (open) {
      setName(isEdit ? (group?.name ?? "") : "");
      setPrefill("");
      setError(null);
    }
  }, [open, isEdit, group?.name]);

  useEffect(() => {
    if (!open || isEdit || !suggestedName || suggestedName === prefill) return;
    // The suggestion lands after the dialog opens; never clobber what was typed.
    setName((current) => (current === prefill ? suggestedName : current));
    setPrefill(suggestedName);
  }, [open, isEdit, suggestedName, prefill]);

  const trimmed = name.trim();
  // An untouched prefill is submitted as blank so the number is allocated at
  // commit time — two admins who both opened the dialog can't claim the same one.
  const isPristinePrefill = !isEdit && !!prefill && trimmed === prefill;
  const submitName = isPristinePrefill ? "" : trimmed;
  // Blank is valid on create (backend auto-names); a rename needs a real,
  // changed name.
  const canSubmit = isEdit ? !!trimmed && trimmed !== group?.name : true;

  const nameHint = isEdit
    ? null
    : nextName.isFetching
      ? "Finding the next available name..."
      : nextName.isError
        ? "Couldn't suggest a name. Leave this blank and one will be generated."
        : null;

  const handleSubmit = async () => {
    if (!canSubmit || isPending) return;
    setError(null);
    try {
      const res =
        isEdit && group
          ? await updateGroup.mutateAsync({ id: group.id, name: trimmed })
          : await createGroup.mutateAsync(
              submitName ? { name: submitName } : {},
            );

      if (!res.data) {
        setError(res.msg || `Failed to ${isEdit ? "rename" : "create"} group.`);
        return;
      }
      toast.success(res.msg || (isEdit ? "Group renamed." : "Group created."));
      onSaved?.(res.data);
      onOpenChange(false);
    } catch (err) {
      // A taken name is the expected failure here, so it belongs inline rather
      // than in a toast the admin has to re-read.
      setError(
        serverMessage(err) ||
          `Failed to ${isEdit ? "rename" : "create"} group.`,
      );
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Rename group" : "Create group"}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Group names must be unique across active groups."
              : "Creates an empty group. Add students from the group's detail view, and a mentor from the matching tools."}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="group-name-input">Group name</Label>
          <Input
            id="group-name-input"
            autoFocus
            value={name}
            onChange={(event) => {
              setName(event.target.value);
              if (error) setError(null);
            }}
            placeholder={
              isEdit
                ? "e.g. Genomics Team A"
                : "Leave blank to auto-generate"
            }
            aria-invalid={!!error}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                void handleSubmit();
              }
            }}
          />
          {nameHint && (
            <p className="text-sm text-muted-foreground">{nameHint}</p>
          )}
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            disabled={isPending}
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button disabled={!canSubmit || isPending} onClick={() => void handleSubmit()}>
            {isPending
              ? isEdit
                ? "Saving..."
                : "Creating..."
              : isEdit
                ? "Save name"
                : "Create group"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
