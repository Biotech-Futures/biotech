// Group detail drawer for viewing/editing group composition

import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import type { Group, Track } from "@/type/group";
import type { TrackOption } from "@/type/user";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useUpdateGroup } from "@/query/group";
import { useState, useEffect, useMemo } from "react";
import { UsersIcon, UserIcon, SaveIcon, XIcon } from "lucide-react";

function getTrackColor(track: Track) {
  switch (track.toLowerCase()) {
    case "frontend":
      return "bg-blue-100 text-blue-800";
    case "backend":
      return "bg-green-100 text-green-800";
    case "fullstack":
      return "bg-purple-100 text-purple-800";
    case "data":
      return "bg-orange-100 text-orange-800";
    default:
      return "bg-slate-100 text-slate-800";
  }
}

interface GroupDetailDrawerProps {
  group: Group | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "view" | "edit";
  tracks?: TrackOption[];
  isLoadingTracks?: boolean;
}

export function GroupDetailDrawer({
  group,
  open,
  onOpenChange,
  mode,
  tracks = [],
  isLoadingTracks = false,
}: GroupDetailDrawerProps) {
  const { mutate: updateGroup, isPending } = useUpdateGroup();
  const [editData, setEditData] = useState<{
    name: string;
    track: Track;
  }>({
    name: "",
    track: "frontend",
  });

  // Reset edit data when group changes
  useEffect(() => {
    if (group) {
      setEditData({
        name: group.name,
        track: group.track,
      });
    }
  }, [group]);

  const trackOptions = useMemo(() => {
    if (tracks.some((item) => item.trackCode === editData.track)) return tracks;
    return [
      ...tracks,
      {
        id: -1,
        trackCode: editData.track,
      },
    ];
  }, [editData.track, tracks]);

  if (!group) return null;

  const handleSave = () => {
    updateGroup(
      {
        id: group.id,
        updates: { name: editData.name, track: editData.track },
      },
      {
        onSuccess: () => {
          onOpenChange(false);
        },
      },
    );
  };

  return (
    <Drawer open={open} onOpenChange={onOpenChange} direction="right">
      <DrawerContent className="w-full sm:max-w-lg">
        <DrawerHeader>
          <DrawerTitle className="flex items-center gap-2">
            {mode === "view" ? (
              <>
                <UsersIcon className="size-5" />
                {group.name}
              </>
            ) : (
              "Edit Group"
            )}
          </DrawerTitle>
          <DrawerDescription>
            {mode === "view"
              ? `View group details and composition`
              : "Modify group name, track, and members"}
          </DrawerDescription>
        </DrawerHeader>

        <div className="mt-6 space-y-6 p-4">
          {/* Group Info */}
          <div className="space-y-4">
            {mode === "view" ? (
              <>
                <div>
                  <Label className="text-muted-foreground">Track</Label>
                  <Badge className={getTrackColor(group.track)}>
                    {group.track}
                  </Badge>
                </div>
                <div>
                  <Label className="text-muted-foreground">Group Name</Label>
                  <p className="font-medium">{group.name}</p>
                </div>
              </>
            ) : (
              <>
                <div>
                  <Label htmlFor="edit-name">Group Name</Label>
                  <Input
                    id="edit-name"
                    value={editData.name}
                    onChange={(e) =>
                      setEditData({ ...editData, name: e.target.value })
                    }
                  />
                </div>
                <div>
                  <Label htmlFor="edit-track">Track</Label>
                  <Select
                    value={editData.track}
                    onValueChange={(value) =>
                      setEditData({ ...editData, track: value as Track })
                    }
                  >
                    <SelectTrigger id="edit-track">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {isLoadingTracks && trackOptions.length === 0 && (
                        <SelectItem value="loading" disabled>
                          Loading tracks...
                        </SelectItem>
                      )}
                      {trackOptions.map((item) => (
                        <SelectItem key={item.id} value={item.trackCode}>
                          {item.trackCode}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </>
            )}
          </div>

          <Separator />

          {/* Mentor */}
          <div className="space-y-2">
            <Label className="flex items-center gap-1 text-muted-foreground">
              <UserIcon className="size-4" />
              Assigned Mentor
            </Label>
            {group.mentor ? (
              <div className="p-3 rounded-md bg-muted/50">
                <p className="font-medium">{group.mentor.name}</p>
                <p className="text-sm text-muted-foreground">
                  {group.mentor.email}
                </p>
              </div>
            ) : (
              <div className="p-3 rounded-md bg-muted/50 text-muted-foreground">
                No mentor assigned
              </div>
            )}
          </div>

          <Separator />

          {/* Members */}
          <div className="space-y-2">
            <Label className="flex items-center gap-1 text-muted-foreground">
              <UsersIcon className="size-4" />
              Group Members ({group.members.length})
            </Label>
            <div className="space-y-2">
              {group.members.map((member) => (
                <div
                  key={member.id}
                  className="flex items-center justify-between p-3 rounded-md bg-muted/50"
                >
                  <div>
                    <p className="font-medium">{member.name}</p>
                    <p className="text-sm text-muted-foreground">
                      {member.email}
                    </p>
                  </div>
                  <Badge variant="outline">{member.role}</Badge>
                </div>
              ))}
            </div>
          </div>

          {/* Actions */}
          {mode === "edit" && (
            <div className="flex gap-2 pt-4">
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                <XIcon className="size-4 mr-1" />
                Cancel
              </Button>
              <Button onClick={handleSave} disabled={isPending}>
                <SaveIcon className="size-4 mr-1" />
                {isPending ? "Saving..." : "Save Changes"}
              </Button>
            </div>
          )}
        </div>
      </DrawerContent>
    </Drawer>
  );
}
