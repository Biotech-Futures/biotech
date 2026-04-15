import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { SaveIcon, XIcon, FileTextIcon } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { Resource, ResourceTypeName } from "@/type/resource";
import {
  getResourceTrackLabel,
  getResourceTypeLabel,
  RESOURCE_TRACKS,
  RESOURCE_TYPES,
} from "@/type/resource";
import { useQueryResourceRoles, useUpdateResource } from "@/query/resource";
import { updateResourceSchema } from "@/schema/resource";

interface ResourceDetailDrawerProps {
  resource: Resource | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "view" | "edit";
  onSwitchToEdit?: () => void;
  onDownload?: (resource: Resource) => void;
}

export function ResourceDetailDrawer({
  resource,
  open,
  onOpenChange,
  mode,
  onSwitchToEdit,
  onDownload,
}: ResourceDetailDrawerProps) {
  const { mutate: updateResource, isPending } = useUpdateResource();
  const { data: rolesData } = useQueryResourceRoles();

  const allRoles = rolesData?.data ?? [];
  const nonAdminRoles = allRoles.filter((role) => role.slug !== "admin");

  const [editData, setEditData] = useState<{
    resource_name: string;
    resource_description: string;
    track_id: number | null;
    resource_type: ResourceTypeName | null;
    role_ids: number[];
  }>({
    resource_name: "",
    resource_description: "",
    track_id: null,
    resource_type: null,
    role_ids: [],
  });

  const visibleRoleSlugs = useMemo(() => {
    if (!resource) return [] as string[];
    const slugs = resource.audiences
      .map((audience) => audience.role?.slug)
      .filter((slug): slug is string => Boolean(slug) && slug !== "admin");
    return Array.from(new Set(slugs));
  }, [resource]);

  useEffect(() => {
    if (!resource) return;

    setEditData({
      resource_name: resource.resource_name,
      resource_description: resource.resource_description ?? "",
      track_id: resource.track_id,
      resource_type: resource.resource_type,
      role_ids: Array.from(
        new Set(
          resource.audiences
            .map((audience) => audience.role_id)
            .filter((roleId): roleId is number => roleId !== null && roleId !== 3),
        ),
      ),
    });
  }, [resource]);

  if (!resource) return null;

  const handleSave = () => {
    const parsed = updateResourceSchema.safeParse({
      resource_name: editData.resource_name,
      resource_description: editData.resource_description,
      track_id: editData.track_id,
      resource_type: editData.resource_type,
      role_ids: editData.role_ids,
    });

    if (!parsed.success) {
      const message = parsed.error.issues[0]?.message ?? "Invalid form data.";
      window.alert(message);
      return;
    }

    updateResource(
      {
        id: resource.id,
        updates: parsed.data,
      },
      {
        onSuccess: () => {
          onOpenChange(false);
        },
      },
    );
  };

  return (
    <Drawer open={open} onOpenChange={onOpenChange} direction="right">
      <DrawerContent className="w-full sm:max-w-lg">
        <DrawerHeader>
          <DrawerTitle className="flex items-center gap-2">
            <FileTextIcon className="size-5" />
            {mode === "view" ? resource.resource_name : "Edit Resource"}
          </DrawerTitle>
          <DrawerDescription>
            {mode === "view"
              ? "View resource details and role visibility"
              : "Update resource metadata and role visibility"}
          </DrawerDescription>
        </DrawerHeader>

        <div className="mt-6 space-y-6 p-4">
          <div className="space-y-4">
            {mode === "view" ? (
              <>
                <div>
                  <Label className="text-muted-foreground">Resource Name</Label>
                  <p className="font-medium">{resource.resource_name}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">Description</Label>
                  <p>{resource.resource_description || "-"}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">Type</Label>
                  <div>
                    <Badge variant="secondary">{getResourceTypeLabel(resource.resource_type)}</Badge>
                  </div>
                </div>
                <div>
                  <Label className="text-muted-foreground">Track</Label>
                  <p>{getResourceTrackLabel(resource.track_id)}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">File</Label>
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
                </div>
              </>
            ) : (
              <>
                <div>
                  <Label htmlFor="resource-name">Resource Name</Label>
                  <Input
                    id="resource-name"
                    value={editData.resource_name}
                    onChange={(event) =>
                      setEditData((prev) => ({ ...prev, resource_name: event.target.value }))
                    }
                  />
                </div>
                <div>
                  <Label htmlFor="resource-description">Description</Label>
                  <Textarea
                    id="resource-description"
                    value={editData.resource_description}
                    onChange={(event) =>
                      setEditData((prev) => ({ ...prev, resource_description: event.target.value }))
                    }
                  />
                </div>
                <div>
                  <Label htmlFor="resource-track">Track</Label>
                  <Select
                    value={editData.track_id === null || editData.track_id === undefined ? "none" : String(editData.track_id)}
                    onValueChange={(value) =>
                      setEditData((prev) => ({
                        ...prev,
                        track_id: value === "none" ? null : Number(value),
                      }))
                    }
                  >
                    <SelectTrigger id="resource-track">
                      <SelectValue placeholder="Select track" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">Unassigned</SelectItem>
                      {RESOURCE_TRACKS.map((track) => (
                        <SelectItem key={track.id} value={String(track.id)}>
                          {track.code}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label htmlFor="resource-type">Type</Label>
                  <Select
                    value={editData.resource_type ?? "none"}
                    onValueChange={(value) =>
                      setEditData((prev) => ({
                        ...prev,
                        resource_type: value === "none" ? null : (value as ResourceTypeName),
                      }))
                    }
                  >
                    <SelectTrigger id="resource-type">
                      <SelectValue placeholder="Select type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">Uncategorized</SelectItem>
                      {RESOURCE_TYPES.map((typeOption) => (
                        <SelectItem key={typeOption.value} value={typeOption.value}>
                          {typeOption.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </>
            )}
          </div>

          <Separator />

          <div className="space-y-2">
            <Label className="text-muted-foreground">Uploader</Label>
            <div className="p-3 rounded-md bg-muted/50">
              <p className="font-medium">
                {`${resource.uploader.first_name} ${resource.uploader.last_name}`.trim()}
              </p>
              <p className="text-sm text-muted-foreground">{resource.uploader.email}</p>
            </div>
          </div>

          <Separator />

          <div className="space-y-2">
            <Label className="text-muted-foreground">Visible Roles</Label>
            {mode === "view" ? (
              <div className="flex flex-wrap gap-2">
                {visibleRoleSlugs.length ? (
                  visibleRoleSlugs.map((slug) => (
                    <Badge key={slug} variant="outline">
                      {slug}
                    </Badge>
                  ))
                ) : (
                  <span className="text-sm text-muted-foreground">Admin default visibility</span>
                )}
              </div>
            ) : (
              <div className="space-y-2">
                {nonAdminRoles.map((role) => {
                  const checked = editData.role_ids.includes(role.id);
                  return (
                    <label key={role.id} className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(event) => {
                          const nextRoleIds = event.target.checked
                            ? [...editData.role_ids, role.id]
                            : editData.role_ids.filter((item) => item !== role.id);

                          setEditData((prev) => ({ ...prev, role_ids: nextRoleIds }));
                        }}
                      />
                      <span>{role.slug}</span>
                    </label>
                  );
                })}
              </div>
            )}
          </div>

          {mode === "view" && (
            <div className="flex gap-2 pt-4">
              <Button onClick={() => onSwitchToEdit?.()}>Edit Resource</Button>
            </div>
          )}

          {mode === "edit" && (
            <div className="flex gap-2 pt-4">
              <Button variant="outline" onClick={() => onOpenChange(false)}>
                <XIcon className="size-4 mr-1" />
                Cancel
              </Button>
              <Button onClick={handleSave} disabled={isPending}>
                <SaveIcon className="size-4 mr-1" />
                {isPending ? "Saving..." : "Save Changes"}
              </Button>
            </div>
          )}
        </div>
      </DrawerContent>
    </Drawer>
  );
}
