import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { MoreHorizontalIcon, PlusIcon, ArchiveIcon, ArchiveRestoreIcon } from "lucide-react";
import {
  useAdminScope,
  useArchiveTrack,
  useCreateTrack,
  useListStates,
  useListTracks,
  useRestoreTrack,
} from "@/query/track";
import { toast } from "sonner";

export const Route = createFileRoute("/_auth/track")({
  component: TrackPage,
});

function TrackPage() {
  const navigate = useNavigate();
  const { data: scope, isPending: scopePending } = useAdminScope();
  const [showArchived, setShowArchived] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);

  useEffect(() => {
    if (!scopePending && scope && !scope.isGlobal) {
      toast.error("Only global admins can manage tracks");
      navigate({ to: "/" });
    }
  }, [scope, scopePending, navigate]);

  const { data: tracks, isPending } = useListTracks(showArchived);
  const { mutateAsync: archive, isPending: archiving } = useArchiveTrack();
  const { mutateAsync: restore, isPending: restoring } = useRestoreTrack();

  const items = tracks ?? [];

  if (scopePending) {
    return <div className="p-4 text-sm text-muted-foreground">Loading...</div>;
  }
  if (scope && !scope.isGlobal) return null;

  async function handleArchive(trackId: number, name: string) {
    if (!window.confirm(`Archive track "${name}"? Users in this track will be blocked from logging in.`)) {
      return;
    }
    try {
      const result = await archive(trackId);
      if (result.data) {
        toast.success(`Archived "${name}"`);
      } else {
        toast.error(result.msg || "Failed to archive");
      }
    } catch {
      toast.error("Failed to archive");
    }
  }

  async function handleRestore(trackId: number, name: string) {
    try {
      const result = await restore(trackId);
      if (result.data) {
        toast.success(`Restored "${name}"`);
      } else {
        toast.error(result.msg || "Failed to restore");
      }
    } catch {
      toast.error("Failed to restore");
    }
  }

  return (
    <div className="min-w-0 space-y-4 p-4">
      <div className="flex flex-wrap items-end justify-between gap-3 p-4">
        <div className="inline-flex rounded-md border p-0.5">
          <Button
            type="button"
            variant={!showArchived ? "default" : "ghost"}
            size="sm"
            onClick={() => setShowArchived(false)}
          >
            Active
          </Button>
          <Button
            type="button"
            variant={showArchived ? "default" : "ghost"}
            size="sm"
            onClick={() => setShowArchived(true)}
          >
            All (incl. archived)
          </Button>
        </div>
        <Button type="button" onClick={() => setCreateOpen(true)}>
          <PlusIcon className="size-4" />
          Create Track
        </Button>
      </div>

      <div className="min-w-0 overflow-hidden rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Track Name</TableHead>
              <TableHead>State</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isPending ? (
              <TableRow>
                <TableCell colSpan={4} className="h-24 text-center">
                  Loading tracks...
                </TableCell>
              </TableRow>
            ) : items.length > 0 ? (
              items.map((track) => (
                <TableRow
                  key={track.id}
                  className={track.isArchived ? "text-muted-foreground bg-muted/30" : ""}
                >
                  <TableCell>{track.trackName}</TableCell>
                  <TableCell>{track.stateName ?? "—"}</TableCell>
                  <TableCell>
                    {track.isArchived ? (
                      <Badge variant="outline">Archived</Badge>
                    ) : (
                      <Badge variant="secondary">Active</Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          aria-label={`Actions for ${track.trackName}`}
                        >
                          <MoreHorizontalIcon className="size-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        {track.isArchived ? (
                          <DropdownMenuItem
                            disabled={restoring}
                            onClick={() => handleRestore(track.id, track.trackName)}
                          >
                            <ArchiveRestoreIcon className="size-4" />
                            Restore
                          </DropdownMenuItem>
                        ) : (
                          <DropdownMenuItem
                            variant="destructive"
                            disabled={archiving}
                            onClick={() => handleArchive(track.id, track.trackName)}
                          >
                            <ArchiveIcon className="size-4" />
                            Archive
                          </DropdownMenuItem>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={4} className="h-24 text-center">
                  No tracks found.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <CreateTrackDialog open={createOpen} onOpenChange={setCreateOpen} />
    </div>
  );
}

function CreateTrackDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [trackName, setTrackName] = useState("");
  const [stateId, setStateId] = useState<string>("");
  const { data: states } = useListStates();
  const { mutateAsync: create, isPending } = useCreateTrack();

  const sortedStates = useMemo(() => states ?? [], [states]);

  useEffect(() => {
    if (!open) {
      setTrackName("");
      setStateId("");
    }
  }, [open]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!trackName.trim() || !stateId) return;
    try {
      const result = await create({
        track_name: trackName.trim(),
        state_id: Number(stateId),
      });
      if (result.data) {
        toast.success("Track created");
        onOpenChange(false);
      } else {
        toast.error(result.msg || "Failed to create track");
      }
    } catch {
      toast.error("Failed to create track");
    }
  }

  const canSubmit = trackName.trim().length > 0 && stateId !== "";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Create Track</DialogTitle>
          <DialogDescription>
            Add a new track. Track names must be unique.
          </DialogDescription>
        </DialogHeader>
        <form id="create-track-form" onSubmit={handleSubmit} className="grid gap-4 px-4 pb-4">
          <div className="grid gap-1.5">
            <Label requiredMarker>Track Name</Label>
            <Input
              placeholder="e.g. AUS-NSW"
              value={trackName}
              onChange={(e) => setTrackName(e.target.value)}
              autoFocus
            />
          </div>
          <div className="grid gap-1.5">
            <Label requiredMarker>State</Label>
            <Select value={stateId} onValueChange={setStateId}>
              <SelectTrigger>
                <SelectValue placeholder="Select a state" />
              </SelectTrigger>
              <SelectContent>
                {sortedStates.map((s) => (
                  <SelectItem key={s.id} value={String(s.id)}>
                    {s.stateName}, {s.countryName}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </form>
        <DialogFooter>
          <Button
            form="create-track-form"
            type="submit"
            disabled={!canSubmit || isPending}
          >
            {isPending ? "Creating..." : "Create"}
          </Button>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
