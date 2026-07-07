import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { RichEditor } from "./RichEditor";
import {
  useAnnouncementGroups,
  useAnnouncementRoles,
  useCreateAnnouncement,
  useUpdateAnnouncement,
} from "@/query/announcement";
import type { Announcement } from "@/type/announcement";
import { toast } from "sonner";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editing?: Announcement | null;
};

export function AnnouncementFormSheet({ open, onOpenChange, editing }: Props) {
  const isEdit = !!editing;

  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [groupIds, setGroupIds] = useState<number[]>([]);
  const [roleIds, setRoleIds] = useState<number[]>([]);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [pendingSendEmail, setPendingSendEmail] = useState(false);

  const { data: groups } = useAnnouncementGroups();
  const { data: roles } = useAnnouncementRoles();
  const { mutateAsync: create, isPending: creating } = useCreateAnnouncement();
  const { mutateAsync: update, isPending: updating } = useUpdateAnnouncement();

  useEffect(() => {
    if (!open) return;
    if (editing) {
      setTitle(editing.title);
      setBody(editing.body ?? "");
      setGroupIds(
        editing.audiences
          .map((a) => a.groupId)
          .filter((id): id is number => id !== null),
      );
      setRoleIds(
        editing.audiences
          .map((a) => a.roleId)
          .filter((id): id is number => id !== null),
      );
    } else {
      setTitle("");
      setBody("");
      setGroupIds([]);
      setRoleIds([]);
    }
  }, [editing, open]);

  function toggleGroup(id: number) {
    setGroupIds((prev) =>
      prev.includes(id) ? prev.filter((g) => g !== id) : [...prev, id],
    );
  }

  function toggleRole(id: number) {
    setRoleIds((prev) =>
      prev.includes(id) ? prev.filter((r) => r !== id) : [...prev, id],
    );
  }

  function buildPayload(sendEmail: boolean) {
    return {
      title,
      body,
      role_ids: roleIds.length > 0 ? roleIds : undefined,
      group_ids: groupIds.length > 0 ? groupIds : undefined,
      send_email: sendEmail,
    };
  }

  async function submit(sendEmail: boolean) {
    try {
      if (isEdit && editing) {
        await update({ id: editing.id, data: buildPayload(sendEmail) });
        toast.success(sendEmail ? "Saved and re-notified" : "Saved");
      } else {
        await create(buildPayload(sendEmail));
        toast.success("Published");
      }
      onOpenChange(false);
    } catch {
      toast.error("Something went wrong");
    }
  }

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="w-[95vw] sm:max-w-5xl max-h-[92vh] overflow-y-auto overflow-x-hidden p-0">
          <DialogHeader className="px-8 pt-7 pb-2 border-b">
            <DialogTitle className="text-xl">
              {isEdit ? "Edit Announcement" : "New Announcement"}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-6 px-8 py-6">
            <div className="space-y-1.5">
              <Label htmlFor="ann-title" requiredMarker>Title</Label>
              <Input
                id="ann-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Announcement title"
              />
            </div>

            <div className="space-y-1.5">
              <Label requiredMarker>Body</Label>
              <RichEditor key={editing?.id ?? "new"} value={body} onChange={setBody} />
            </div>

            {(roles?.length ?? 0) > 0 && (
              <div className="space-y-2">
                <Label>Target Roles</Label>
                <div className="grid grid-cols-2 gap-2">
                  {roles!.map((r) => (
                    <label
                      key={r.id}
                      className="flex items-center gap-2 text-sm cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={roleIds.includes(r.id)}
                        onChange={() => toggleRole(r.id)}
                      />
                      {r.name}
                    </label>
                  ))}
                </div>
                {roleIds.length > 0 && (
                  <p className="text-xs text-muted-foreground">
                    {roleIds.length} role{roleIds.length > 1 ? "s" : ""} selected
                  </p>
                )}
              </div>
            )}

            {(groups?.length ?? 0) > 0 && (
              <div className="space-y-2">
                <Label>Target Groups</Label>
                <div className="grid grid-cols-2 gap-2">
                  {groups!.map((g) => (
                    <label
                      key={g.id}
                      className="flex items-center gap-2 text-sm cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={groupIds.includes(g.id)}
                        onChange={() => toggleGroup(g.id)}
                      />
                      {g.name}
                    </label>
                  ))}
                </div>
                {groupIds.length > 0 && (
                  <p className="text-xs text-muted-foreground">
                    {groupIds.length} group{groupIds.length > 1 ? "s" : ""} selected
                  </p>
                )}
              </div>
            )}

            {groupIds.length === 0 && roleIds.length === 0 && (
              <p className="text-xs text-muted-foreground">
                No roles or groups selected — announcement will be visible to all users.
              </p>
            )}
          </div>

          <DialogFooter className="px-8 pb-7 pt-2 border-t flex gap-2">
            {isEdit ? (
              <>
                <Button
                  variant="outline"
                  onClick={() => submit(false)}
                  disabled={updating || creating}
                >
                  Save
                </Button>
                <Button
                  onClick={() => submit(true)}
                  disabled={updating || creating}
                >
                  Save & Re-notify
                </Button>
              </>
            ) : (
              <Button
                onClick={() => {
                  setPendingSendEmail(true);
                  setConfirmOpen(true);
                }}
                disabled={creating}
              >
                Publish & Notify
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Publish this announcement?</AlertDialogTitle>
            <AlertDialogDescription>
              This will immediately publish the announcement to the platform and
              send an email notification to the selected audience.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                setConfirmOpen(false);
                submit(pendingSendEmail);
              }}
            >
              Publish & Notify
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
