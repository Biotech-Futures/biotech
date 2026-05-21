import type { ColumnDef } from "@tanstack/react-table";
import {
  getResourceTrackLabel,
  getResourceTypeLabel,
  type Resource,
  type ResourceTrackOption,
} from "@/type/resource";
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
  onAccess?: (resource: Resource) => void;
  onDownload?: (resource: Resource) => void;
  trackOptions?: ResourceTrackOption[];
}

const truncatingCellClassName = "truncate";

function formatUploaderName(resource: Resource) {
  return `${resource.uploader.first_name} ${resource.uploader.last_name}`.trim();
}

function getVisibleRoleSlugs(resource: Resource) {
  const slugs = resource.audiences
    .map((audience) => audience.role?.slug)
    .filter((slug): slug is string => Boolean(slug) && slug !== "admin");
  return Array.from(new Set(slugs));
}

function parseResourceDate(value: string | null | undefined) {
  if (!value) return Number.NaN;
  let normalized = value.includes("T") ? value : value.replace(" ", "T");
  normalized = normalized
    .replace(/([+-]\d{2})$/, "$1:00")
    .replace(/([+-]\d{2})(\d{2})$/, "$1:$2");
  const hasTimezone = /(?:Z|[+-]\d{2}:\d{2})$/i.test(normalized);
  if (!hasTimezone) normalized = `${normalized}Z`;
  return Date.parse(normalized);
}

export function createResourceColumns({
  onViewDetail,
  onEdit,
  onDelete,
  onDownload,
  trackOptions,
}: ResourceColumnsOptions = {}): ColumnDef<Resource>[] {
  const trackLabelById = new Map(
    (trackOptions ?? []).map((item) => [item.id, item.label]),
  );

  return [
    {
      accessorKey: "name",
      header: "Resource",
      meta: {
        headClassName: "",
        cellClassName: truncatingCellClassName,
      },
      cell: ({ row }) => {
        const resource = row.original;
        return (
          <button
            className="block w-full truncate font-medium hover:underline text-left"
            onClick={() => onViewDetail?.(resource)}
          >
            {resource.name}
          </button>
        );
      },
    },
    {
      id: "type_name",
      accessorFn: (row) => getResourceTypeLabel(row.type_name),
      header: "Type",
      meta: {
        headClassName: "",
        cellClassName: truncatingCellClassName,
      },
      cell: ({ row }) => {
        return <span>{getResourceTypeLabel(row.original.type_name)}</span>;
      },
    },
    {
      id: "visibility",
      accessorFn: (row) => row.visibility_scope,
      header: "Visibility",
      meta: {
        headClassName: "",
        cellClassName: truncatingCellClassName,
      },
      cell: ({ row }) => {
        return <span>{row.original.visibility_scope}</span>;
      },
    },
    {
      id: "role",
      accessorFn: (row) => getVisibleRoleSlugs(row).join(", "),
      header: "Role",
      meta: {
        headClassName: "",
        cellClassName: truncatingCellClassName,
      },
      cell: ({ row }) => {
        const roleSlugs = getVisibleRoleSlugs(row.original);
        if (!roleSlugs.length) {
          return <span className="text-muted-foreground text-sm">-</span>;
        }
        return <span>{roleSlugs.join(", ")}</span>;
      },
    },
    {
      id: "track",
      accessorFn: (row) => {
        const trackId = Number(row.track_id);
        return Number.isFinite(trackId)
          ? (trackLabelById.get(trackId) ?? getResourceTrackLabel(trackId))
          : "Unassigned";
      },
      header: "Track",
      meta: {
        headClassName: "",
        cellClassName: truncatingCellClassName,
      },
      cell: ({ row }) => {
        const rawTrackId = row.original.track_id;
        if (rawTrackId === null || rawTrackId === undefined)
          return <span>Unassigned</span>;
        const trackId = Number(rawTrackId);
        if (!Number.isFinite(trackId)) return <span>Unassigned</span>;
        return (
          <span>
            {trackLabelById.get(trackId) ?? getResourceTrackLabel(trackId)}
          </span>
        );
      },
    },
    {
      id: "uploader",
      accessorFn: formatUploaderName,
      header: "Uploader",
      meta: {
        headClassName: "",
        cellClassName: truncatingCellClassName,
      },
      cell: ({ row }) => {
        return <span>{formatUploaderName(row.original)}</span>;
      },
    },
    {
      accessorKey: "uploaded_at",
      header: "Uploaded Time",
      meta: {
        headClassName: "",
        cellClassName: truncatingCellClassName,
      },
      cell: ({ row }) => {
        const parsed = parseResourceDate(row.original.uploaded_at);
        if (Number.isNaN(parsed))
          return <span className="text-muted-foreground">N/A</span>;
        return new Date(parsed).toLocaleString();
      },
    },
    {
      id: "actions",
      enableSorting: false,
      meta: {
        headClassName: "w-[56px]",
        cellClassName: "align-top w-[56px]",
      },
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
              {/* {resource.file_name ? (
                <DropdownMenuItem onClick={() => onAccess?.(resource)}>
                  Access Resource
                </DropdownMenuItem>
              ) : null} */}
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
