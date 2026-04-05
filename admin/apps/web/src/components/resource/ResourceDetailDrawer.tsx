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
import { SaveIcon, XIcon, FileTextIcon, UserIcon } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { Resource, ResourceTypeName } from "@/type/resource";
import { RESOURCE_TYPES } from "@/type/resource";
import { useQueryResourceRoles, useUpdateResource } from "@/query/resource";
import { updateResourceSchema } from "@/schema/resource";

interface ResourceDetailDrawerProps {
  resource: Resource | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "view" | "edit";
  onSwitchToEdit?: () => void;
}

export function ResourceDetailDrawer({
  resource,
  open,
  onOpenChange,
  mode,
  onSwitchToEdit,
}: ResourceDetailDrawerProps) {
  const { mutate: updateResource, isPending } = useUpdateResource();
  const { data: rolesData } = useQueryResourceRoles();

  const allRoles = rolesData?.data ?? [];

  const [editData, setEditData] = useState<{
    resource_name: string;
    resource_description: string;
    resource_type_id: string | null;
    role_ids: string[];
  }>({
    resource_name: "",
    resource_description: "",
    resource_type_id: null,
    role_ids: [],
  });

  const typeIdByName = useMemo(() => {
    return {
      document: "type-1",
      guide: "type-2",
      video: "type-3",
      template: "type-4",
    } as Record<ResourceTypeName, string>;
  }, []);

  useEffect(() => {
    if (!resource) return;

    setEditData({
      resource_name: resource.resource_name,
      resource_description: resource.resource_description,
      resource_type_id: resource.resource_type_detail
        ? typeIdByName[resource.resource_type_detail.type_name]
        : null,
      role_ids: resource.visible_roles.map((role) => role.id),
    });
  }, [resource, typeIdByName]);

  if (!resource) return null;

  const handleSave = () => {
    const parsed = updateResourceSchema.safeParse({
      resource_name: editData.resource_name,
      resource_description: editData.resource_description,
      resource_type_id: editData.resource_type_id,
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
                  <p>{resource.resource_description}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">Type</Label>
                  <div>
                    <Badge variant="secondary">
                      {resource.resource_type_detail?.type_name ?? "uncategorized"}
                    </Badge>
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
                  <Label htmlFor="resource-type">Type</Label>
                  <Select
                    value={editData.resource_type_id ?? "none"}
                    onValueChange={(value) =>
                      setEditData((prev) => ({
                        ...prev,
                        resource_type_id: value === "none" ? null : value,
                      }))
                    }
                  >
                    <SelectTrigger id="resource-type">
                      <SelectValue placeholder="Select type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">Uncategorized</SelectItem>
                      {RESOURCE_TYPES.map((typeName) => (
                        <SelectItem key={typeName} value={typeIdByName[typeName]}>
                          {typeName.charAt(0).toUpperCase() + typeName.slice(1)}
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
            <Label className="flex items-center gap-1 text-muted-foreground">
              <UserIcon className="size-4" />
              Uploader
            </Label>
            <div className="p-3 rounded-md bg-muted/50">
              <p className="font-medium">{`${resource.uploader.first_name} ${resource.uploader.last_name}`}</p>
              <p className="text-sm text-muted-foreground">{resource.uploader.email}</p>
            </div>
          </div>

          <Separator />

          <div className="space-y-2">
            <Label className="text-muted-foreground">Visible Roles</Label>
            {mode === "view" ? (
              <div className="flex flex-wrap gap-2">
                {resource.visible_roles.length ? (
                  resource.visible_roles.map((role) => (
                    <Badge key={role.id} variant="outline">
                      {role.role_name}
                    </Badge>
                  ))
                ) : (
                  <span className="text-sm text-muted-foreground">No role restriction</span>
                )}
              </div>
            ) : (
              <div className="space-y-2">
                {allRoles.map((role) => {
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
                      <span>{role.role_name}</span>
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
