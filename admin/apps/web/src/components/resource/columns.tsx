import type { ColumnDef } from "@tanstack/react-table";
import type { Resource } from "@/type/resource";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { MoreHorizontal, FileText, UserIcon } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { ResourceTypeName } from "@/type/resource";

interface ResourceColumnsOptions {
  onViewDetail?: (resource: Resource) => void;
  onEdit?: (resource: Resource) => void;
  onDelete?: (resource: Resource) => void;
}

function formatType(typeName?: string) {
  if (!typeName) return "Uncategorized";
  return typeName.charAt(0).toUpperCase() + typeName.slice(1);
}

const typeColors: Record<ResourceTypeName, string> = {
  document: "bg-blue-100 text-blue-800",
  guide: "bg-emerald-100 text-emerald-800",
  video: "bg-amber-100 text-amber-800",
  template: "bg-violet-100 text-violet-800",
};

export function createResourceColumns({
  onViewDetail,
  onEdit,
  onDelete,
}: ResourceColumnsOptions = {}): ColumnDef<Resource>[] {
  return [
    {
      accessorKey: "resource_name",
      header: "Resource",
      cell: ({ row }) => {
        const resource = row.original;
        return (
          <button
            className="font-medium hover:underline text-left"
            onClick={() => onViewDetail?.(resource)}
          >
            {resource.resource_name}
          </button>
        );
      },
    },
    {
      id: "resource_type_detail",
      header: "Type",
      cell: ({ row }) => {
        const type = row.original.resource_type_detail?.type_name;
        if (!type) {
          return <Badge variant="secondary">Uncategorized</Badge>;
        }
        return <Badge className={typeColors[type]}>{formatType(type)}</Badge>;
      },
    },
    {
      id: "visible_roles",
      header: () => (
        <div className="flex items-center gap-1">
          <FileText className="size-4" />
          Visibility
        </div>
      ),
      cell: ({ row }) => {
        const roles = row.original.visible_roles;
        if (!roles.length) {
          return <span className="text-muted-foreground text-sm">No role restriction</span>;
        }
        return <span>{roles.map((role) => role.role_name).join(", ")}</span>;
      },
    },
    {
      id: "uploader",
      header: () => (
        <div className="flex items-center gap-1">
          <UserIcon className="size-4" />
          Uploader
        </div>
      ),
      cell: ({ row }) => {
        const uploader = row.original.uploader;
        return <span>{`${uploader.first_name} ${uploader.last_name}`}</span>;
      },
    },
    {
      accessorKey: "upload_datetime",
      header: "Uploaded",
      cell: ({ row }) => {
        const parsed = Date.parse(row.original.upload_datetime ?? "");
        if (Number.isNaN(parsed)) return <span className="text-muted-foreground">N/A</span>;
        return new Date(parsed).toLocaleString();
      },
    },
    {
      id: "actions",
      cell: ({ row }) => {
        const resource = row.original;

        return (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon">
                <MoreHorizontal className="size-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => onViewDetail?.(resource)}>
                View Details
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onEdit?.(resource)}>
                Edit Resource
              </DropdownMenuItem>
              <DropdownMenuItem
                className="text-red-600"
                onClick={() => onDelete?.(resource)}
              >
                Delete Resource
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        );
      },
    },
  ];
}
