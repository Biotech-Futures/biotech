import type { ColumnDef } from "@tanstack/react-table";
import { getResourceTrackLabel, getResourceTypeLabel, type Resource } from "@/type/resource";
import { Button } from "@/components/ui/button";
import { MoreHorizontal } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface ResourceColumnsOptions {
  onViewDetail?: (resource: Resource) => void;
  onEdit?: (resource: Resource) => void;
  onDelete?: (resource: Resource) => void;
  onDownload?: (resource: Resource) => void;
}

function formatUploaderName(resource: Resource) {
  return `${resource.uploader.first_name} ${resource.uploader.last_name}`.trim();
}

function getVisibleRoleSlugs(resource: Resource) {
  const slugs = resource.audiences
    .map((audience) => audience.role?.slug)
    .filter((slug): slug is string => Boolean(slug) && slug !== "admin");
  return Array.from(new Set(slugs));
}

export function createResourceColumns({
  onViewDetail,
  onEdit,
  onDelete,
  onDownload,
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
      id: "resource_type",
      header: "Type",
      cell: ({ row }) => {
        return <span>{getResourceTypeLabel(row.original.resource_type)}</span>;
      },
    },
    {
      id: "visibility",
      header: "Visibility",
      cell: ({ row }) => {
        const roleSlugs = getVisibleRoleSlugs(row.original);
        if (!roleSlugs.length) {
          return <span className="text-muted-foreground text-sm">Admin default visibility</span>;
        }
        return <span>{roleSlugs.join(", ")}</span>;
      },
    },
    {
      id: "track_id",
      header: "Track",
      cell: ({ row }) => <span>{getResourceTrackLabel(row.original.track_id)}</span>,
    },
    {
      id: "uploader",
      header: "Uploader",
      cell: ({ row }) => {
        return <span>{formatUploaderName(row.original)}</span>;
      },
    },
    {
      accessorKey: "uploaded_at",
      header: "Uploaded",
      cell: ({ row }) => {
        const parsed = Date.parse(row.original.uploaded_at ?? "");
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
              {resource.file_name ? (
                <DropdownMenuItem onClick={() => onDownload?.(resource)}>
                  Download File
                </DropdownMenuItem>
              ) : null}
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
