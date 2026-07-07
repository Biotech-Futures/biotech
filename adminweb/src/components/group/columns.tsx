// Group table columns definition

import type { ColumnDef } from "@tanstack/react-table";
import type { Group } from "@/type/group";
import { Button } from "@/components/ui/button";
import { UsersIcon, UserIcon } from "lucide-react";

interface ColumnsOptions {
  onViewDetail?: (group: Group) => void;
  onViewMessages?: (group: Group) => void;
}

export function createColumns({
  onViewDetail,
  onViewMessages,
}: ColumnsOptions = {}): ColumnDef<Group>[] {
  return [
    {
      accessorKey: "name",
      header: "Group Name",
      cell: ({ row }) => {
        const group = row.original;
        return (
          <button
            className="font-medium hover:underline text-left"
            onClick={() => onViewDetail?.(group)}
          >
            {group.name}
          </button>
        );
      },
    },
    {
      id: "members",
      accessorFn: (row) => row.members.length,
      header: () => (
        <div className="flex items-center gap-1">
          <UsersIcon className="size-4" />
          Members
        </div>
      ),
      cell: ({ row }) => {
        const members = row.original.members;
        return <span>{members.length} students</span>;
      },
    },
    {
      id: "mentor",
      accessorFn: (row) => row.mentor?.name ?? "",
      header: () => (
        <div className="flex items-center gap-1">
          <UserIcon className="size-4" />
          Mentor
        </div>
      ),
      cell: ({ row }) => {
        const mentor = row.original.mentor;
        return mentor ? (
          <span className="font-medium">{mentor.name}</span>
        ) : (
          <span className="text-muted-foreground">No mentor assigned</span>
        );
      },
    },
    {
      accessorKey: "createdAt",
      header: "Created",
      cell: ({ row }) => {
        return new Date(row.getValue("createdAt")).toLocaleDateString();
      },
    },
    {
      id: "messages",
      header: "Messages",
      cell: ({ row }) => {
        const group = row.original;

        return (
          <Button
            variant="outline"
            size="sm"
            onClick={() => onViewMessages?.(group)}
          >
            View Messages
          </Button>
        );
      },
    },
  ];
}
