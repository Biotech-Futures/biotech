import { useMemo, useState } from "react";
import {
  Sheet,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useQueryResourceRoles, useQueryResourceTypes, useUploadResource } from "@/query/resource";
import type { ResourceTypeName } from "@/type/resource";
import { RESOURCE_TRACKS } from "@/type/resource";

interface ResourceUploadSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ResourceUploadSheet({ open, onOpenChange }: ResourceUploadSheetProps) {
  const { data: rolesData } = useQueryResourceRoles();
  const { data: typesData } = useQueryResourceTypes();
  const { mutate: uploadResource, isPending } = useUploadResource();

  const [resourceName, setResourceName] = useState("");
  const [resourceDescription, setResourceDescription] = useState("");
  const [resourceType, setResourceType] = useState<ResourceTypeName | "">("");
  const [trackId, setTrackId] = useState<string>("");
  const [roleIds, setRoleIds] = useState<number[]>([]);
  const [file, setFile] = useState<File | null>(null);

  const roles = rolesData?.data ?? [];
  const types = typesData?.data ?? [];

  const fileSizeText = useMemo(() => {
    if (!file) return "";
    const kb = file.size / 1024;
    if (kb < 1024) return `${kb.toFixed(1)} KB`;
    return `${(kb / 1024).toFixed(1)} MB`;
  }, [file]);

  const resetForm = () => {
    setResourceName("");
    setResourceDescription("");
    setResourceType("");
    setTrackId("");
    setRoleIds([]);
    setFile(null);
  };

  const handleSubmit = () => {
    if (!file) {
      window.alert("Please choose a file first.");
      return;
    }
    if (!resourceName.trim()) {
      window.alert("Resource name is required.");
      return;
    }
    if (!resourceDescription.trim()) {
      window.alert("Resource description is required.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("resource_name", resourceName.trim());
    formData.append("resource_description", resourceDescription.trim());
    if (resourceType) formData.append("resource_type", resourceType);
    if (trackId) formData.append("track_id", trackId);
    roleIds.forEach((roleId) => formData.append("role_ids", String(roleId)));

    uploadResource(formData, {
      onSuccess: () => {
        resetForm();
        onOpenChange(false);
      },
    });
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>Upload Resource</SheetTitle>
        </SheetHeader>

        <div className="space-y-4 px-4">
          <div className="space-y-1.5">
            <Label htmlFor="resource-file">File</Label>
            <Input
              id="resource-file"
              type="file"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
            {file ? (
              <p className="text-xs text-muted-foreground">
                {file.name} ({fileSizeText})
              </p>
            ) : null}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="upload-resource-name">Resource Name</Label>
            <Input
              id="upload-resource-name"
              value={resourceName}
              onChange={(event) => setResourceName(event.target.value)}
              placeholder="e.g. Mentor Handbook 2026"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="upload-resource-description">Description</Label>
            <Textarea
              id="upload-resource-description"
              value={resourceDescription}
              onChange={(event) => setResourceDescription(event.target.value)}
              placeholder="Short description for admins and users."
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="upload-resource-track">Track</Label>
            <Select value={trackId || "none"} onValueChange={(value) => setTrackId(value === "none" ? "" : value)}>
              <SelectTrigger id="upload-resource-track">
                <SelectValue placeholder="Select track" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">Unassigned</SelectItem>
                {RESOURCE_TRACKS.map((track) => (
                  <SelectItem key={track.id} value={String(track.id)}>
                    {track.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="upload-resource-type">Type</Label>
            <Select
              value={resourceType || "none"}
              onValueChange={(value) => setResourceType(value === "none" ? "" : (value as ResourceTypeName))}
            >
              <SelectTrigger id="upload-resource-type">
                <SelectValue placeholder="Select type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">Uncategorized</SelectItem>
                {types.map((typeItem) => (
                  <SelectItem key={typeItem.value} value={typeItem.value}>
                    {typeItem.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Visible Roles</Label>
            <div className="space-y-2">
              {roles
                .filter((role) => role.slug !== "admin")
                .map((role) => {
                  const checked = roleIds.includes(role.id);
                  return (
                    <label key={role.id} className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(event) => {
                          setRoleIds((prev) =>
                            event.target.checked
                              ? [...prev, role.id]
                              : prev.filter((item) => item !== role.id),
                          );
                        }}
                      />
                      <span>{role.slug}</span>
                    </label>
                  );
                })}
            </div>
          </div>
        </div>

        <SheetFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={isPending}>
            {isPending ? "Uploading..." : "Upload"}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}
