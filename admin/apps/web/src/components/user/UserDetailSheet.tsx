import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
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
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>{user.name || "User Details"}</SheetTitle>
        </SheetHeader>

        <div className="space-y-6 px-4 pb-4">
          <DetailSection
            title="Account"
            items={[
              { label: "Email", value: user.email || "-" },
              { label: "Role", value: <Badge variant="outline">{labelizeUserRole(user.role)}</Badge> },
              { label: "Track", value: labelizeTrack(user.track) },
              {
                label: "Status",
                value: (
                  <Badge variant={user.active ? "default" : "secondary"}>
                    {user.active ? "Active" : "Inactive"}
                  </Badge>
                ),
              },
              { label: "Source", value: user.source },
            ]}
          />

          <DetailSection
            title="Student Profile"
            items={[
              { label: "School", value: user.schoolName || "-" },
              { label: "Age / Year Level", value: user.age ?? "-" },
              {
                label: "Join Permission",
                value: user.joinPermissionReceived ? "Received" : "Not received",
              },
              {
                label: "Interests",
                value: user.interests.length ? user.interests.join(", ") : "-",
              },
              { label: "Group", value: user.groupName || "-" },
            ]}
          />
        </div>
      </SheetContent>
    </Sheet>
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
      <div className="space-y-3 rounded-md border p-4">
        {items.map((item) => (
          <div
            key={item.label}
            className="flex flex-col gap-1 border-b pb-3 last:border-b-0 last:pb-0"
          >
            <span className="text-xs uppercase tracking-wide text-muted-foreground">
              {item.label}
            </span>
            <div className="text-sm text-foreground">{item.value}</div>
          </div>
        ))}
      </div>
    </section>
  );
}
