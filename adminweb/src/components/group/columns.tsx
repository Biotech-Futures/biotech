// Group table columns definition

import type { ColumnDef } from "@tanstack/react-table";
import type { Group, Track } from "@/type/group";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ArrowUpDown, RotateCcwIcon, Trash2Icon, UsersIcon, UserIcon } from "lucide-react";

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

interface ColumnsOptions {
  onViewDetail?: (group: Group) => void;
  onViewMessages?: (group: Group) => void;
  onDelete?: (group: Group) => void;
  onRestore?: (group: Group) => void;
  recoveryMode?: boolean;
}

export function createColumns({
  onViewDetail,
  onViewMessages,
  onDelete,
  onRestore,
  recoveryMode = false,
}: ColumnsOptions = {}): ColumnDef<Group>[] {
  const columns: ColumnDef<Group>[] = [
    {
      accessorKey: "name",
      header: ({ column }) => {
        return (
          <Button
            variant="ghost"
            onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
          >
            Group Name
            <ArrowUpDown className="ml-2 size-4" />
          </Button>
        );
      },
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
      accessorKey: "track",
      header: "Track",
      cell: ({ row }) => {
        const track = row.getValue("track") as Track;
        return <Badge className={getTrackColor(track)}>{track}</Badge>;
      },
      filterFn: (row, id, value) => {
        return value.includes(row.getValue(id));
      },
    },
    {
      id: "members",
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
  ];

  if (recoveryMode) {
    columns.push({
      id: "deletedAt",
      header: "Deleted",
      cell: ({ row }) => {
        const deletedAt = row.original.deletedAt;
        return deletedAt ? new Date(deletedAt).toLocaleString() : "-";
      },
    });
    columns.push({
      id: "restore",
      header: "Actions",
      cell: ({ row }) => {
        const group = row.original;
        return (
          <Button variant="outline" size="sm" onClick={() => onRestore?.(group)}>
            <RotateCcwIcon className="size-4" />
            Restore
          </Button>
        );
      },
    });
    return columns;
  }

  columns.push({
    id: "messages",
    header: "Actions",
    cell: ({ row }) => {
      const group = row.original;

      return (
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onViewMessages?.(group)}
          >
            View Messages
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="text-destructive hover:text-destructive"
            aria-label={`Delete ${group.name}`}
            onClick={() => onDelete?.(group)}
          >
            <Trash2Icon className="size-4" />
          </Button>
        </div>
      );
    },
  });

  return columns;
}
