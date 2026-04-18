// Group detail drawer for viewing/editing group composition

import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import type { Group, Track } from "@/type/group";
import { Label } from "@/components/ui/label";
import { UserIcon, UsersIcon } from "lucide-react";

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
}

export function GroupDetailDrawer({
  group,
  open,
  onOpenChange,
}: GroupDetailDrawerProps) {
  if (!group) return null;

  return (
    <Drawer open={open} onOpenChange={onOpenChange} direction="right">
      <DrawerContent className="h-full w-full overflow-hidden sm:max-w-lg">
        <DrawerHeader className="shrink-0">
          <DrawerTitle className="flex items-center gap-2">
            <UsersIcon className="size-5" />
            {group.name}
          </DrawerTitle>
          <DrawerDescription>
            View group details and composition
          </DrawerDescription>
        </DrawerHeader>

        <div className="min-h-0 flex-1 space-y-6 overflow-y-auto p-4">
          {/* Group Info */}
          <div className="space-y-4">
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
        </div>
      </DrawerContent>
    </Drawer>
  );
}
