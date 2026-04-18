import type { ColumnDef } from "@tanstack/react-table";
import type { StudentUser } from "@/type/user";
import { Badge } from "@/components/ui/badge";
import { Link } from "@tanstack/react-router";

export const studentColumns: ColumnDef<StudentUser>[] = [
  {
    accessorKey: "name",
    header: "Student",
    cell: ({ row }) => {
      const { name, email, groupId } = row.original;
      const content = (
        <div className="min-w-0">
          <p className="truncate font-medium">{name}</p>
          <p className="truncate text-xs text-muted-foreground">{email}</p>
        </div>
      );

      if (!groupId) return content;

      return (
        <Link
          to="/group"
          search={{ groupId }}
          className="text-primary font-medium underline-offset-2 hover:underline"
          title={`Open group details for ${groupId}`}
        >
          {content}
        </Link>
      );
    },
  },
  {
    id: "school",
    header: "School",
    cell: ({ row }) => row.original.studentInfo.schoolName ?? "-",
  },
  {
    id: "yearLevel",
    header: "Year",
    cell: ({ row }) => {
      const yearLevel = row.original.studentInfo.yearLevel;
      return yearLevel ? `Year ${yearLevel}` : "-";
    },
  },
  {
    accessorKey: "track",
    header: "Track",
    cell: ({ row }) => row.original.track ?? "-",
  },
  {
    id: "group",
    header: "Group",
    cell: ({ row }) => {
      const { groupInfo } = row.original;
      if (!groupInfo) return "-";

      return (
        <Link
          to="/group"
          search={{ groupId: String(groupInfo.id) }}
          className="text-primary underline-offset-2 hover:underline"
          title={`Open group details for ${groupInfo.id}`}
        >
          {groupInfo.name}
        </Link>
      );
    },
  },
  {
    accessorKey: "interests",
    header: "Interests",
    cell: ({ row }) => {
      const items = row.original.interests;
      if (!items.length) return "-";

      return (
        <div className="flex max-w-sm flex-wrap gap-1">
          {items.map((item) => (
            <Badge key={item.id} variant="outline">
              {item.description}
            </Badge>
          ))}
        </div>
      );
    },
  },
  {
    id: "permission",
    header: "Permission",
    cell: ({ row }) => (
      <Badge
        variant={
          row.original.studentInfo.joinPermissionReceived
            ? "default"
            : "secondary"
        }
      >
        {row.original.studentInfo.joinPermissionReceived
          ? "Received"
          : "Missing"}
      </Badge>
    ),
  },
];
