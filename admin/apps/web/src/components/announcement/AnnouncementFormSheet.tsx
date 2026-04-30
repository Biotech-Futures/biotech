import { useState, useEffect } from "react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetFooter,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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

type VisibilityScope = "global" | "track_based" | "role_based";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editing?: Announcement | null;
};

export function AnnouncementFormSheet({ open, onOpenChange, editing }: Props) {
  const isEdit = !!editing;

  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [scope, setScope] = useState<VisibilityScope>("global");
  const [trackId, setTrackId] = useState<number | null>(null);
  const [roleIds, setRoleIds] = useState<number[]>([]);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [pendingSendEmail, setPendingSendEmail] = useState(false);

  const { data: tracks } = useAnnouncementTracks();
  const { data: roles } = useAnnouncementRoles();
  const { mutateAsync: create, isPending: creating } = useCreateAnnouncement();
  const { mutateAsync: update, isPending: updating } = useUpdateAnnouncement();

  useEffect(() => {
    if (editing) {
      setTitle(editing.title);
      setBody(editing.body ?? "");
      setScope(editing.visibilityScope as VisibilityScope);
      setTrackId(editing.trackId);
      setRoleIds(
        editing.audiences
          .map((a) => a.roleId)
          .filter((id): id is number => id !== null),
      );
    } else {
      setTitle("");
      setBody("");
      setScope("global");
      setTrackId(null);
      setRoleIds([]);
    }
  }, [editing, open]);

  function toggleRole(id: number) {
    setRoleIds((prev) =>
      prev.includes(id) ? prev.filter((r) => r !== id) : [...prev, id],
    );
  }

  function buildPayload(sendEmail: boolean) {
    return {
      title,
      body,
      visibility_scope: scope,
      track_id: scope === "track_based" ? (trackId ?? undefined) : undefined,
      role_ids: scope === "role_based" ? roleIds : undefined,
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
        toast.success("Published and notified");
      }
      onOpenChange(false);
    } catch {
      toast.error("Something went wrong");
    }
  }

  // Create: one button → confirm dialog → publish + email
  // Edit: Save (no email) + Save & Re-notify (with email)

  return (
    <>
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent className="w-full sm:max-w-2xl overflow-y-auto">
          <SheetHeader>
            <SheetTitle>
              {isEdit ? "Edit Announcement" : "New Announcement"}
            </SheetTitle>
          </SheetHeader>

          <div className="space-y-5 py-4">
            <div className="space-y-1.5">
              <Label htmlFor="ann-title">Title</Label>
              <Input
                id="ann-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Announcement title"
              />
            </div>

            <RichEditor value={body} onChange={setBody} />

            <div className="space-y-1.5">
              <Label>Audience</Label>
              <Select
                value={scope}
                onValueChange={(v) => setScope(v as VisibilityScope)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="global">All users</SelectItem>
                  <SelectItem value="track_based">By track</SelectItem>
                  <SelectItem value="role_based">By role</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {scope === "track_based" && (
              <div className="space-y-1.5">
                <Label>Track</Label>
                <Select
                  value={trackId ? String(trackId) : ""}
                  onValueChange={(v) => setTrackId(Number(v))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select track" />
                  </SelectTrigger>
                  <SelectContent>
                    {tracks?.map((t) => (
                      <SelectItem key={t.id} value={String(t.id)}>
                        {t.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {scope === "role_based" && (
              <div className="space-y-1.5">
                <Label>Roles</Label>
                <div className="flex flex-wrap gap-2">
                  {roles?.map((r) => (
                    <button
                      key={r.id}
                      type="button"
                      onClick={() => toggleRole(r.id)}
                      className={`rounded-full border px-3 py-1 text-sm transition-colors ${
                        roleIds.includes(r.id)
                          ? "border-primary bg-primary text-primary-foreground"
                          : "border-border bg-background text-foreground hover:bg-accent"
                      }`}
                    >
                      {r.name}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          <SheetFooter className="flex gap-2">
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
          </SheetFooter>
        </SheetContent>
      </Sheet>

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
