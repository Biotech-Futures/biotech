import type { ColumnDef } from "@tanstack/react-table";
import type { StudentUser } from "@/type/user";
import { Badge } from "@/components/ui/badge";
import { Link } from "@tanstack/react-router";

export const studentColumns: ColumnDef<StudentUser>[] = [
  {
    id: "name",
    header: "Student",
    cell: ({ row }) => {
      const { firstName, lastName, email, groupId } = row.original;
      const name = `${firstName} ${lastName}`.trim();
      const content = (
        <div className="min-w-0">
          <p className="truncate font-medium">{name}</p>
          <p className="truncate text-xs text-muted-foreground">{email}</p>
        </div>
      );

      return content;
    },
  },
  {
    id: "school",
    header: "School",
    cell: ({ row }) => row.original.schoolName ?? "-",
  },
  {
    id: "yearLevel",
    header: "Year",
    cell: ({ row }) => {
      const yearLevel = row.original.yearLevel;
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
      const { groupId, groupName } = row.original;
      if (!groupId || !groupName) return "-";

      return (
        <Link
          to="/group"
          search={{ page: 1, groupId: String(groupId) }}
          className="text-primary underline-offset-2 hover:underline"
          title={`Open group details for ${groupId}`}
        >
          {groupName}
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
];
