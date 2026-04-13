import type { ColumnDef } from "@tanstack/react-table";
import type { StudentUser } from "@/type/user";
import { Badge } from "@/components/ui/badge";
import { Link } from "@tanstack/react-router";

export const studentColumns: ColumnDef<StudentUser>[] = [
  {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => {
      const { name, groupId } = row.original;
      if (!groupId) return name;

      return (
        <Link
          to="/group"
          search={{ groupId }}
          className="text-primary font-medium underline-offset-2 hover:underline"
          title={`Open group details for ${groupId}`}
        >
          {name}
        </Link>
      );
    },
  },
  {
    accessorKey: "email",
    header: "Email",
  },
  {
    accessorKey: "age",
    header: "Age",
    cell: ({ row }) => row.original.age ?? "-",
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
      if (!groupId) return "-";

      return (
        <Link
          to="/group"
          search={{ groupId }}
          className="text-primary underline-offset-2 hover:underline"
          title={`Open group details for ${groupId}`}
        >
          {groupName ?? groupId}
        </Link>
      );
    },
  },
  {
    accessorKey: "interests",
    header: "Interest",
    cell: ({ row }) => {
      const items = row.original.interests;
      return items.length ? items.join(", ") : "-";
    },
  },
  {
    id: "inGroup",
    header: "In Group",
    cell: ({ row }) => (
      <Badge variant={row.original.groupId ? "default" : "secondary"}>
        {row.original.groupId ? "Yes" : "No"}
      </Badge>
    ),
  },
];
