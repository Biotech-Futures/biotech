import type { ColumnDef } from "@tanstack/react-table";
import type { StudentUser } from "@/type/user";
import { Badge } from "@/components/ui/badge";
import { Link } from "@tanstack/react-router";

export const studentColumns: ColumnDef<StudentUser>[] = [
  {
    id: "name",
    accessorFn: (row) => `${row.firstName} ${row.lastName}`.trim(),
    header: "Student",
    cell: ({ row }) => {
      const { firstName, lastName, email } = row.original;
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
    accessorFn: (row) => row.schoolName ?? "",
    header: "School",
    cell: ({ row }) => row.original.schoolName ?? "-",
  },
  {
    id: "yearLevel",
    accessorFn: (row) => row.yearLevel ?? 0,
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
    accessorFn: (row) => row.groupName ?? "",
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
    sortingFn: (a, b) =>
      a.original.interests.join(", ").localeCompare(b.original.interests.join(", ")),
    cell: ({ row }) => {
      const items = row.original.interests;
      if (!items.length) return "-";

      return (
        <div className="flex max-w-sm flex-wrap gap-1">
          {items.map((item, index) => (
            <Badge key={index} variant="outline">
              {item}
            </Badge>
          ))}
        </div>
      );
    },
  },
];
