// Group table columns definition

import type { ColumnDef } from "@tanstack/react-table";
import type { Group, Track } from "@/type/group";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ArrowUpDown, MoreHorizontal, UsersIcon, UserIcon } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const trackColors: Record<Track, string> = {
  frontend: "bg-blue-100 text-blue-800",
  backend: "bg-green-100 text-green-800",
  fullstack: "bg-purple-100 text-purple-800",
  data: "bg-orange-100 text-orange-800",
};

interface ColumnsOptions {
  onViewDetail?: (group: Group) => void;
  onEdit?: (group: Group) => void;
}

export function createColumns({ onViewDetail, onEdit }: ColumnsOptions = {}): ColumnDef<Group>[] {
  return [
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
        return <Badge className={trackColors[track]}>{track}</Badge>;
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
    {
      id: "actions",
      cell: ({ row }) => {
        const group = row.original;

        return (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon">
                <MoreHorizontal className="size-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => onViewDetail?.(group)}>
                View Details
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onEdit?.(group)}>
                Edit Group
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        );
      },
    },
  ];
}