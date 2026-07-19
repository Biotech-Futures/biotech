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
import { useCreateGroup, useUpdateGroup } from "@/query/group";
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
  const [error, setError] = useState<string | null>(null);

  const createGroup = useCreateGroup();
  const updateGroup = useUpdateGroup();
  const isPending = isEdit ? updateGroup.isPending : createGroup.isPending;

  useEffect(() => {
    if (open) {
      setName(isEdit ? (group?.name ?? "") : "");
      setError(null);
    }
  }, [open, isEdit, group?.name]);

  const trimmed = name.trim();
  // Blank is valid on create (backend auto-names BTF_<id>); a rename needs a real,
  // changed name.
  const canSubmit = isEdit ? !!trimmed && trimmed !== group?.name : true;

  const handleSubmit = async () => {
    if (!canSubmit || isPending) return;
    setError(null);
    try {
      const res =
        isEdit && group
          ? await updateGroup.mutateAsync({ id: group.id, name: trimmed })
          : await createGroup.mutateAsync(trimmed ? { name: trimmed } : {});

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
                : "Leave blank to auto-generate (BTF_0042)"
            }
            aria-invalid={!!error}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                void handleSubmit();
              }
            }}
          />
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
