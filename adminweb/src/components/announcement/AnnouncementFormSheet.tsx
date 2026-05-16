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
  useAnnouncementTracks,
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
  const [trackIds, setTrackIds] = useState<number[]>([]);
  const [roleIds, setRoleIds] = useState<number[]>([]);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [pendingSendEmail, setPendingSendEmail] = useState(false);

  const { data: tracks } = useAnnouncementTracks();
  const { data: roles } = useAnnouncementRoles();
  const { mutateAsync: create, isPending: creating } = useCreateAnnouncement();
  const { mutateAsync: update, isPending: updating } = useUpdateAnnouncement();

  useEffect(() => {
    if (!open) return;
    if (editing) {
      setTitle(editing.title);
      setBody(editing.body ?? "");
      const existingTrackIds = editing.audiences
        .map((a) => a.trackId)
        .filter((id): id is number => id !== null);
      setTrackIds(existingTrackIds.length > 0 ? existingTrackIds : (editing.trackId ? [editing.trackId] : []));
      setRoleIds(
        editing.audiences
          .map((a) => a.roleId)
          .filter((id): id is number => id !== null),
      );
    } else {
      setTitle("");
      setBody("");
      setTrackIds([]);
      setRoleIds([]);
    }
  }, [editing, open]);

  function toggleTrack(id: number) {
    setTrackIds((prev) =>
      prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id],
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
      track_ids: trackIds.length > 0 ? trackIds : undefined,
      role_ids: roleIds.length > 0 ? roleIds : undefined,
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
              <Label htmlFor="ann-title">Title</Label>
              <Input
                id="ann-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Announcement title"
              />
            </div>

            <RichEditor key={editing?.id ?? "new"} value={body} onChange={setBody} />

            {(tracks?.length ?? 0) > 0 && (
              <div className="space-y-2">
                <Label>Target Tracks</Label>
                <div className="grid grid-cols-2 gap-2">
                  {tracks!.map((t) => (
                    <label
                      key={t.id}
                      className="flex items-center gap-2 text-sm cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={trackIds.includes(t.id)}
                        onChange={() => toggleTrack(t.id)}
                      />
                      {t.name}
                    </label>
                  ))}
                </div>
                {trackIds.length > 0 && (
                  <p className="text-xs text-muted-foreground">
                    {trackIds.length} track{trackIds.length > 1 ? "s" : ""} selected
                  </p>
                )}
              </div>
            )}

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

            {trackIds.length === 0 && roleIds.length === 0 && (
              <p className="text-xs text-muted-foreground">
                No tracks or roles selected — announcement will be visible to all users.
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
