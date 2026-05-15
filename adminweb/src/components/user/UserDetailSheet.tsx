import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { labelizeTrack, labelizeUserRole, type UserAccount } from "@/type/user";

interface UserDetailSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  user: UserAccount | null;
}

export function UserDetailSheet({
  open,
  onOpenChange,
  user,
}: UserDetailSheetProps) {
  if (!user) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[92vh] flex-col overflow-hidden sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{user.name || "User Details"}</DialogTitle>
        </DialogHeader>

        <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-4 pb-4">
          <DetailSection
            title="Account"
            items={[
              { label: "Email", value: user.email || "-" },
              {
                label: "Role",
                value: user.role ? (
                  <Badge variant="outline">{labelizeUserRole(user.role)}</Badge>
                ) : (
                  <span className="text-muted-foreground">—</span>
                ),
              },
              { label: "Track", value: labelizeTrack(user.track) },
              {
                label: "Status",
                value: (
                  <Badge variant={user.active ? "default" : "secondary"}>
                    {user.active ? "Active" : "Inactive"}
                  </Badge>
                ),
              },
            ]}
          />

          {user.role === "student" && (
            <DetailSection
              title="Student Profile"
              items={[
                { label: "School", value: user.schoolName || "-" },
                { label: "Year Level", value: user.age ?? "-" },
                {
                  label: "Join Permission",
                  value: user.joinPermissionReceived
                    ? "Received"
                    : "Not received",
                },
                {
                  label: "Interests",
                  value: user.interests.length
                    ? user.interests.join(", ")
                    : "-",
                },
                { label: "Group", value: user.groupName || "-" },
              ]}
            />
          )}

          {user.role === "mentor" && (
            <DetailSection
              title="Mentor Profile"
              items={[
                {
                  label: "Interests / Expertise",
                  value: user.interests.length
                    ? user.interests.join(", ")
                    : "-",
                },
                { label: "Institution", value: user.mentorInstitution || "-" },
                { label: "Background", value: user.mentorBackground || "-" },
                { label: "Mentor Reason", value: user.mentorReason || "-" },
                { label: "Max Groups", value: user.mentorMaxGroupCount ?? "-" },
                { label: "Group", value: user.groupName || "-" },
              ]}
            />
          )}

          {user.role === "supervisor" && (
            <DetailSection
              title="Supervisor Profile"
              items={[
                { label: "School", value: user.schoolName || "-" },
                { label: "Group", value: user.groupName || "-" },
              ]}
            />
          )}

          {user.role === "admin" && (
            <DetailSection
              title="Admin Profile"
              items={[
                {
                  label: "Scope",
                  value: user.adminIsGlobal ? "Global admin" : "Track admin",
                },
                {
                  label: "Managed Tracks",
                  value: user.adminTracks.length
                    ? user.adminTracks.join(", ")
                    : "-",
                },
              ]}
            />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function DetailSection({
  title,
  items,
}: {
  title: string;
  items: Array<{ label: string; value: ReactNode }>;
}) {
  return (
    <section className="space-y-3">
      <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      <div className="space-y-3 rounded-md">
        {items.map((item) => (
          <div
            key={item.label}
            className="grid gap-1.5 last:border-b-0 last:pb-0 sm:grid-cols-[140px_minmax(0,1fr)] sm:items-start sm:gap-4"
          >
            <span className="text-xs uppercase tracking-wide text-muted-foreground sm:text-left">
              {item.label}
            </span>
            <div className="min-w-0 text-sm text-foreground">{item.value}</div>
          </div>
        ))}
      </div>
    </section>
  );
}
