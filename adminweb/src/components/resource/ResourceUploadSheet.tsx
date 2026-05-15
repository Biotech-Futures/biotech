import { useMemo, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  useCreateResource,
  useQueryResourceRoles,
  useQueryResourceTracks,
  useQueryResourceTypes,
  useUploadResource,
} from "@/query/resource";
import type { ResourceKind, ResourceTypeName } from "@/type/resource";
import { RichEditor } from "@/components/announcement/RichEditor";

type VisibilityMode = "global" | "track_based" | "role_based";

interface ResourceUploadSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ResourceUploadSheet({
  open,
  onOpenChange,
}: ResourceUploadSheetProps) {
  const { data: rolesData } = useQueryResourceRoles();
  const { data: tracksData } = useQueryResourceTracks();
  const { data: typesData } = useQueryResourceTypes();
  const { mutate: uploadResource, isPending: isUploadPending } =
    useUploadResource();
  const { mutate: createResource, isPending: isCreatePending } =
    useCreateResource();

  const [resourceName, setResourceName] = useState("");
  const [resourceDescription, setResourceDescription] = useState("");
  const [resourceKind, setResourceKind] = useState<ResourceKind>("file");
  const [visibilityMode, setVisibilityMode] =
    useState<VisibilityMode>("role_based");
  const [resourceType, setResourceType] = useState<ResourceTypeName | "">("");
  const [trackId, setTrackId] = useState<string>("");
  const [roleIds, setRoleIds] = useState<number[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [contentHtml, setContentHtml] = useState("");

  const roles = rolesData?.data ?? [];
  const tracks = tracksData?.data ?? [];
  const types = typesData?.data ?? [];

  const fileSizeText = useMemo(() => {
    if (!file) return "";
    const kb = file.size / 1024;
    if (kb < 1024) return `${kb.toFixed(1)} KB`;
    return `${(kb / 1024).toFixed(1)} MB`;
  }, [file]);

  const getErrorMessage = (error: unknown) => {
    if (
      typeof error === "object" &&
      error !== null &&
      "response" in error &&
      typeof (error as { response?: unknown }).response === "object" &&
      (error as { response?: { data?: unknown } }).response?.data &&
      typeof (error as { response?: { data?: { msg?: unknown } } }).response
        ?.data?.msg === "string"
    ) {
      return (
        (error as { response?: { data?: { msg?: string } } }).response?.data
          ?.msg ?? "Request failed."
      );
    }

    if (error instanceof Error) return error.message;
    return "Request failed. Please try again.";
  };

  const resetForm = () => {
    setResourceName("");
    setResourceDescription("");
    setResourceKind("file");
    setVisibilityMode("role_based");
    setResourceType("");
    setTrackId("");
    setRoleIds([]);
    setFile(null);
    setContentHtml("");
  };

  const handleSubmit = () => {
    if (!resourceName.trim()) {
      window.alert("Resource name is required.");
      return;
    }
    if (!resourceDescription.trim()) {
      window.alert("Resource description is required.");
      return;
    }
    const parsedTrackId = trackId ? Number(trackId) : null;
    const finalTrackId = Number.isFinite(parsedTrackId) ? parsedTrackId : null;
    const finalRoleIds = roleIds;

    if (visibilityMode === "track_based" && finalTrackId === null) {
      window.alert("Track is required for track-based visibility.");
      return;
    }

    if (visibilityMode === "role_based" && !finalRoleIds.length) {
      window.alert(
        "Please select at least one role for role-based visibility.",
      );
      return;
    }

    if (resourceKind === "page") {
      if (!contentHtml.trim()) {
        window.alert("HTML content is required for page resources.");
        return;
      }

      createResource(
        {
          resource_name: resourceName.trim(),
          resource_description: resourceDescription.trim(),
          resource_kind: "page",
          content_html: contentHtml.trim(),
          visibility_scope: visibilityMode,
          resource_type: resourceType || "guide",
          track_id: finalTrackId ?? undefined,
          role_ids: finalRoleIds,
        },
        {
          onSuccess: () => {
            resetForm();
            onOpenChange(false);
          },
          onError: (error) => {
            window.alert(getErrorMessage(error));
          },
        },
      );
      return;
    }

    if (!file) {
      window.alert("Please choose a file first.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("resource_name", resourceName.trim());
    formData.append("resource_description", resourceDescription.trim());
    formData.append("visibility_scope", visibilityMode);
    if (resourceType) formData.append("resource_type", resourceType);
    if (finalTrackId !== null) {
      formData.append("track_id", String(finalTrackId));
    }
    if (roleIds.length) {
      roleIds.forEach((roleId) => formData.append("role_ids", String(roleId)));
    }

    uploadResource(formData, {
      onSuccess: () => {
        resetForm();
        onOpenChange(false);
      },
      onError: (error) => {
        window.alert(getErrorMessage(error));
      },
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[92vh] w-[95vw] max-w-[calc(100%-2rem)] flex-col gap-0 overflow-hidden p-0 sm:max-w-3xl">
        <DialogHeader className="shrink-0 border-b px-6 py-4 pr-12">
          <DialogTitle>Upload Resource</DialogTitle>
        </DialogHeader>

        <div className="min-h-0 flex-1 overflow-y-auto space-y-4 px-4 py-4">
          <div className="space-y-1.5">
            <Label htmlFor="resource-kind">Resource Kind</Label>
            <Select
              value={resourceKind}
              onValueChange={(value) => setResourceKind(value as ResourceKind)}
            >
              <SelectTrigger id="resource-kind">
                <SelectValue placeholder="Select resource mode" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="file">File Upload</SelectItem>
                <SelectItem value="page">Rich Content Page</SelectItem>
              </SelectContent>
            </Select>
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
            <Label htmlFor="upload-visibility-mode">Visibility</Label>
            <Select
              value={visibilityMode}
              onValueChange={(value) =>
                setVisibilityMode(value as VisibilityMode)
              }
            >
              <SelectTrigger id="upload-visibility-mode">
                <SelectValue placeholder="Select visibility mode" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="track_based">Track-based</SelectItem>
                <SelectItem value="role_based">Role-based</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="upload-resource-track">Track</Label>
            <Select
              value={trackId || "none"}
              onValueChange={(value) =>
                setTrackId(value === "none" ? "" : value)
              }
            >
              <SelectTrigger id="upload-resource-track">
                <SelectValue placeholder="Select track" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">Unassigned</SelectItem>
                {tracks.map((track) => (
                  <SelectItem key={track.id} value={String(track.id)}>
                    {track.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {visibilityMode === "track_based" ? (
              <p className="text-xs text-muted-foreground">
                Required for track-based visibility.
              </p>
            ) : null}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="upload-resource-type">Type</Label>
            <Select
              value={resourceType || "none"}
              onValueChange={(value) =>
                setResourceType(
                  value === "none" ? "" : (value as ResourceTypeName),
                )
              }
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
                    <label
                      key={role.id}
                      className="flex items-center gap-2 text-sm"
                    >
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
            <p className="text-xs text-muted-foreground">
              {visibilityMode === "role_based"
                ? "Select one or more roles."
                : "Roles are preserved for future role-based switching."}
            </p>
          </div>

          {resourceKind === "file" ? (
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
          ) : null}

          {resourceKind === "page" ? (
            <div className="space-y-1.5">
              <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  {/* <Button
                    type="button"
                    variant="default"
                    size="sm"
                    onClick={() => openHtmlPreviewPage(contentHtml)}
                  >
                    Open Preview Page
                  </Button> */}
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setContentHtml("")}
                  >
                    Clear
                  </Button>
                </div>
              </div>
              <RichEditor
                value={contentHtml}
                onChange={setContentHtml}
                placeholder="Write resource page content..."
              />
            </div>
          ) : null}
        </div>

        <DialogFooter className="mx-0 mb-0 shrink-0 rounded-none border-t px-4 py-4">
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            type="button"
            onClick={handleSubmit}
            disabled={isUploadPending || isCreatePending}
          >
            {isUploadPending || isCreatePending
              ? "Saving..."
              : resourceKind === "page"
                ? "Create Page"
                : "Upload"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
