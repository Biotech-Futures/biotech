// Group table columns definition

import type { ColumnDef } from "@tanstack/react-table";
import type { Group } from "@/type/group";
import { Button } from "@/components/ui/button";
import { UsersIcon, UserIcon, Trash2Icon, PencilIcon } from "lucide-react";

interface ColumnsOptions {
  onViewDetail?: (group: Group) => void;
  onViewMessages?: (group: Group) => void;
  onRename?: (group: Group) => void;
  onDelete?: (group: Group) => void;
}

export function createColumns({
  onViewDetail,
  onViewMessages,
  onRename,
  onDelete,
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
      header: "Actions",
      cell: ({ row }) => {
        const group = row.original;

        return (
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => onViewMessages?.(group)}
            >
              View Messages
            </Button>
            {onRename ? (
              <Button
                variant="ghost"
                size="sm"
                aria-label={`Rename ${group.name}`}
                onClick={() => onRename(group)}
              >
                <PencilIcon className="size-4" />
              </Button>
            ) : null}
            {onDelete ? (
              <Button
                variant="ghost"
                size="sm"
                className="text-destructive hover:text-destructive"
                aria-label={`Delete ${group.name}`}
                onClick={() => onDelete(group)}
              >
                <Trash2Icon className="size-4" />
              </Button>
            ) : null}
          </div>
        );
      },
    },
  ];
}
