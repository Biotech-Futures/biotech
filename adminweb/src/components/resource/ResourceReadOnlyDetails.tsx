import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import type { ReactNode } from "react";
import type {
  Resource,
  ResourceKind,
  ResourceRole,
  ResourceTrackOption,
} from "@/type/resource";
import { getResourceTrackLabel, getResourceTypeLabel } from "@/type/resource";
import { ResourceRoleSelector } from "./ResourceRoleSelector";
import { RichEditor } from "@/components/announcement/RichEditor";

function getResourceKindLabel(kind: ResourceKind) {
  if (kind === "attachment") return "Attachment";
  if (kind === "page") return "Rich Content Page";
  return "File";
}

interface ResourceReadOnlyDetailsProps {
  resource: Resource;
  roles: ResourceRole[];
  trackOptions: ResourceTrackOption[];
  onDownload?: (resource: Resource) => void;
}

interface ResourceDetailRowProps {
  label: string;
  children: ReactNode;
}

function ResourceDetailRow({ label, children }: ResourceDetailRowProps) {
  return (
    <div className="grid gap-2 sm:grid-cols-[9rem_minmax(0,1fr)] sm:items-start">
      <Label className="pt-0.5 text-sm font-medium text-muted-foreground">
        {label}
      </Label>
      <div className="min-w-0">{children}</div>
    </div>
  );
}

export function ResourceReadOnlyDetails({
  resource,
  roles,
  trackOptions,
  onDownload,
}: ResourceReadOnlyDetailsProps) {
  const pageContentHtml = resource.content_html?.trim() || "";
  const trackId = Number(resource.track_id);
  const trackLabel =
    resource.track_id === null ||
    resource.track_id === undefined ||
    !Number.isFinite(trackId)
      ? "Unassigned"
      : trackOptions.find((item) => item.id === trackId)?.label ??
        getResourceTrackLabel(trackId);
  const visibleRoleSlugs = Array.from(
    new Set(
      resource.audiences
        .map((audience) => audience.role?.slug)
        .filter((slug): slug is string => Boolean(slug) && slug !== "admin"),
    ),
  );

  return (
    <div className="space-y-4">
      <ResourceDetailRow label="Resource Name">
        <p className="font-medium">{resource.name}</p>
      </ResourceDetailRow>

      <ResourceDetailRow label="Description">
        <div className="rounded-md border bg-muted/20 px-3 py-2">
          <p className="whitespace-pre-wrap text-sm leading-relaxed">
            {resource.description || "-"}
          </p>
        </div>
      </ResourceDetailRow>

      <ResourceDetailRow label="Type">
        <div>
          <Badge variant="secondary">
            {getResourceTypeLabel(resource.type_name)}
          </Badge>
        </div>
      </ResourceDetailRow>

      <ResourceDetailRow label="Kind">
        <p>{getResourceKindLabel(resource.kind)}</p>
      </ResourceDetailRow>

      <ResourceDetailRow label="Visibility">
        <p>{resource.visibility_scope}</p>
      </ResourceDetailRow>

      {resource.visibility_scope === "track_based" ? (
        <ResourceDetailRow label="Track">
          <p>{trackLabel}</p>
        </ResourceDetailRow>
      ) : null}

      {resource.visibility_scope === "role_based" ||
      resource.visibility_scope === "global" ? (
        <ResourceDetailRow label="Visible Roles">
          <ResourceRoleSelector
            mode="view"
            roles={roles}
            visibleRoleSlugs={visibleRoleSlugs}
            visibilityScope={resource.visibility_scope}
          />
        </ResourceDetailRow>
      ) : null}

      {resource.kind === "page" ? (
        <ResourceDetailRow label="Page Content">
          <RichEditor
            value={pageContentHtml || "<p>No content yet.</p>"}
            readOnly
          />
        </ResourceDetailRow>
      ) : (
        <ResourceDetailRow label="File">
          <div className="flex items-center justify-between gap-2">
            <p>{resource.file_name ?? "No file metadata"}</p>
            {resource.file_name ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() => onDownload?.(resource)}
              >
                Download
              </Button>
            ) : null}
          </div>
        </ResourceDetailRow>
      )}
    </div>
  );
}
