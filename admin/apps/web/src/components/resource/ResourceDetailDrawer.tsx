import {
  Drawer,
  DrawerContent,
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
import type { Resource, ResourceKind, ResourceTypeName } from "@/type/resource";
import {
  getResourceTrackLabel,
  getResourceTypeLabel,
  RESOURCE_TRACKS,
  RESOURCE_TYPES,
} from "@/type/resource";
import {
  useQueryResourceRoles,
  useQueryResourceTracks,
  useQueryResourceTypes,
  useReplaceResourceFile,
  useUpdateResource,
} from "@/query/resource";
import { updateResourceSchema } from "@/schema/resource";

type VisibilityMode = "global" | "track_based" | "role_based";

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
  const { mutateAsync: updateResourceAsync, isPending } = useUpdateResource();
  const { mutateAsync: replaceResourceFileAsync, isPending: isReplacingFile } =
    useReplaceResourceFile();
  const { data: rolesData } = useQueryResourceRoles();
  const { data: tracksData } = useQueryResourceTracks();
  const { data: typesData } = useQueryResourceTypes();

  const allRoles = rolesData?.data ?? [];
  const nonAdminRoles = allRoles.filter((role) => role.slug !== "admin");
  const trackOptions = tracksData?.data?.length ? tracksData.data : RESOURCE_TRACKS;
  const typeOptions = typesData?.data?.length
    ? typesData.data.map((item) => ({ value: item.value, label: item.label }))
    : RESOURCE_TYPES;

  const [editData, setEditData] = useState<{
    name: string;
    description: string;
    kind: ResourceKind;
    visibility_mode: VisibilityMode;
    track_id: number | null;
    type_name: ResourceTypeName | null;
    content_html: string;
    role_ids: number[];
  }>({
    name: "",
    description: "",
    kind: "file",
    visibility_mode: "role_based",
    track_id: null,
    type_name: null,
    content_html: "",
    role_ids: [],
  });
  const [htmlFileName, setHtmlFileName] = useState("");
  const [replacementFile, setReplacementFile] = useState<File | null>(null);
  const [showHtmlEditor, setShowHtmlEditor] = useState(false);
  const [showHtmlPreview, setShowHtmlPreview] = useState(false);

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
      name: resource.name,
      description: resource.description ?? "",
      kind: resource.kind,
      visibility_mode:
        resource.visibility_scope === "global" ||
        resource.visibility_scope === "track_based" ||
        resource.visibility_scope === "role_based"
          ? (resource.visibility_scope as VisibilityMode)
          : resource.audiences.some((audience) => audience.role?.slug !== "admin")
            ? "role_based"
            : resource.track_id !== null
              ? "track_based"
              : "role_based",
      track_id: resource.track_id,
      type_name: resource.type_name,
      content_html: resource.content_html ?? "",
      role_ids: Array.from(
        new Set(
          resource.audiences
            .map((audience) => audience.role_id)
            .filter((roleId): roleId is number => roleId !== null && roleId !== 3),
        ),
      ),
    });
    setHtmlFileName("");
    setReplacementFile(null);
    setShowHtmlEditor(false);
    setShowHtmlPreview(false);
  }, [resource]);

  if (!resource) return null;

  const handleSave = async () => {
    if (editData.visibility_mode === "track_based" && editData.track_id === null) {
      window.alert("Track is required for track-based visibility.");
      return;
    }

    if (editData.visibility_mode === "role_based" && !editData.role_ids.length) {
      window.alert("Please select at least one role for role-based visibility.");
      return;
    }
    const finalTrackId =
      editData.visibility_mode === "track_based" ? editData.track_id : null;
    const finalRoleIds =
      editData.visibility_mode === "role_based" ? editData.role_ids : [];

    const parsed = updateResourceSchema.safeParse({
      resource_name: editData.name,
      resource_description: editData.description,
      resource_kind: editData.kind,
      visibility_scope: editData.visibility_mode,
      track_id: finalTrackId,
      resource_type: editData.type_name,
      content_html: editData.content_html || null,
      role_ids: finalRoleIds,
    });

    if (!parsed.success) {
      const message = parsed.error.issues[0]?.message ?? "Invalid form data.";
      window.alert(message);
      return;
    }

    try {
      await updateResourceAsync({
        id: resource.id,
        updates: parsed.data,
      });

      if (replacementFile && editData.kind === "file") {
        const formData = new FormData();
        formData.append("file", replacementFile);
        await replaceResourceFileAsync({
          id: resource.id,
          payload: formData,
        });
      }

      onOpenChange(false);
    } catch {
      window.alert("Save failed. Please try again.");
    }
  };

  const handleChooseHtmlFile = async (selectedFile: File | null) => {
    if (!selectedFile) {
      setHtmlFileName("");
      return;
    }

    try {
      const htmlText = await selectedFile.text();
      setHtmlFileName(selectedFile.name);
      setEditData((prev) => ({
        ...prev,
        content_html: htmlText,
      }));
    } catch {
      window.alert("Failed to read the HTML file.");
    }
  };

  const openHtmlPreviewPage = (html: string) => {
    const documentHtml = `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Resource Preview</title>
    <style>
      body { margin: 0; padding: 24px; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; color: #111827; background: #f8fafc; }
      .wrap { max-width: 960px; margin: 0 auto; background: white; border: 1px solid #e5e7eb; border-radius: 12px; padding: 20px; box-shadow: 0 1px 2px rgba(0,0,0,.04); }
    </style>
  </head>
  <body>
    <div class="wrap">
      ${html || "<p>No content yet.</p>"}
    </div>
  </body>
</html>`;

    const blob = new Blob([documentHtml], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const win = window.open(url, "_blank");
    if (!win) {
      window.alert("Preview tab was blocked. Please allow pop-ups for this site.");
      return;
    }
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  };

  return (
    <Drawer open={open} onOpenChange={onOpenChange} direction="right">
      <DrawerContent className="w-full sm:max-w-lg h-dvh max-h-dvh min-h-0 overflow-hidden">
        <DrawerHeader className="shrink-0 border-b">
          <DrawerTitle className="flex items-center gap-2">
            <FileTextIcon className="size-5" />
            {mode === "view" ? resource.name : "Edit Resource"}
          </DrawerTitle>
        </DrawerHeader>

        <div
          data-vaul-no-drag
          className="min-h-0 flex-1 overflow-y-auto overscroll-contain space-y-6 p-4 pb-24"
        >
          <div className="space-y-4">
            {mode === "view" ? (
              <>
                <div>
                  <Label className="text-muted-foreground">Resource Name</Label>
                  <p className="font-medium">{resource.name}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">Description</Label>
                  <div className="mt-2 rounded-md border bg-muted/20 px-3 py-2">
                    <p className="whitespace-pre-wrap text-sm leading-relaxed">
                      {resource.description || "-"}
                    </p>
                  </div>
                </div>
                <div>
                  <Label className="text-muted-foreground">Type</Label>
                  <div>
                    <Badge variant="secondary">{getResourceTypeLabel(resource.type_name)}</Badge>
                  </div>
                </div>
                <div>
                  <Label className="text-muted-foreground">Kind</Label>
                  <p>{resource.kind === "page" ? "HTML Page" : "File"}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">Track</Label>
                  <p>{getResourceTrackLabel(resource.track_id)}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">Visibility</Label>
                  <p>{resource.visibility_scope}</p>
                </div>
                {resource.kind === "page" ? (
                  <div>
                    <Label className="text-muted-foreground">Page Preview</Label>
                    <div className="mt-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          openHtmlPreviewPage(resource.content_html || "<p>No content yet.</p>")
                        }
                      >
                        Open Preview Page
                      </Button>
                    </div>
                  </div>
                ) : (
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
                )}
              </>
            ) : (
              <>
                <div>
                  <Label htmlFor="resource-name">Resource Name</Label>
                  <Input
                    id="resource-name"
                    value={editData.name}
                    onChange={(event) =>
                      setEditData((prev) => ({ ...prev, name: event.target.value }))
                    }
                  />
                </div>
                <div>
                  <Label htmlFor="resource-description">Description</Label>
                  <Textarea
                    id="resource-description"
                    value={editData.description}
                    onChange={(event) =>
                      setEditData((prev) => ({ ...prev, description: event.target.value }))
                    }
                  />
                </div>
                <div>
                  <Label htmlFor="resource-kind">Kind</Label>
                  <Select
                    value={editData.kind}
                    onValueChange={(value) =>
                      setEditData((prev) => ({
                        ...prev,
                        kind: value as ResourceKind,
                      }))
                    }
                  >
                    <SelectTrigger id="resource-kind">
                      <SelectValue placeholder="Select kind" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="file">File</SelectItem>
                      <SelectItem value="page">HTML Page</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label htmlFor="resource-visibility-mode">Visibility</Label>
                  <Select
                    value={editData.visibility_mode}
                    onValueChange={(value) =>
                      setEditData((prev) => ({
                        ...prev,
                        visibility_mode: value as VisibilityMode,
                      }))
                    }
                  >
                    <SelectTrigger id="resource-visibility-mode">
                      <SelectValue placeholder="Select visibility mode" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="global">Global</SelectItem>
                      <SelectItem value="track_based">Track-based</SelectItem>
                      <SelectItem value="role_based">Role-based</SelectItem>
                    </SelectContent>
                  </Select>
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
                      {trackOptions.map((track) => (
                        <SelectItem key={track.id} value={String(track.id)}>
                          {track.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {editData.visibility_mode === "track_based"
                      ? "Required for track-based visibility."
                      : "Optional for global/role-based visibility."}
                  </p>
                </div>
                <div>
                  <Label htmlFor="resource-type">Type</Label>
                  <Select
                    value={editData.type_name ?? "none"}
                    onValueChange={(value) =>
                      setEditData((prev) => ({
                        ...prev,
                        type_name: value === "none" ? null : (value as ResourceTypeName),
                      }))
                    }
                  >
                    <SelectTrigger id="resource-type">
                      <SelectValue placeholder="Select type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">Uncategorized</SelectItem>
                      {typeOptions.map((typeOption) => (
                        <SelectItem key={typeOption.value} value={typeOption.value}>
                          {typeOption.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                {editData.kind === "page" ? (
                  <div>
                    <div className="space-y-2">
                      <Label htmlFor="resource-content-html">HTML Content</Label>
                      <div className="flex flex-wrap items-center gap-2">
                        <Button
                          type="button"
                          variant="default"
                          size="sm"
                          onClick={() => openHtmlPreviewPage(editData.content_html)}
                        >
                          Open Preview Page
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() =>
                            setEditData((prev) => ({ ...prev, content_html: "" }))
                          }
                        >
                          Clear
                        </Button>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => setShowHtmlEditor((prev) => !prev)}
                        >
                          {showHtmlEditor ? "Hide Editor" : "Show Editor"}
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => setShowHtmlPreview((prev) => !prev)}
                        >
                          {showHtmlPreview ? "Hide Preview" : "Show Preview"}
                        </Button>
                      </div>
                    </div>
                    <div className="mt-3 space-y-1.5">
                      <Label htmlFor="edit-resource-html-file">HTML File</Label>
                      <Input
                        id="edit-resource-html-file"
                        type="file"
                        accept=".html,.htm,text/html"
                        onChange={(event) =>
                          handleChooseHtmlFile(event.target.files?.[0] ?? null)
                        }
                      />
                      {htmlFileName ? (
                        <p className="text-xs text-muted-foreground">{htmlFileName}</p>
                      ) : (
                        <p className="text-xs text-muted-foreground">
                          Upload an HTML file or edit content manually below.
                        </p>
                      )}
                    </div>
                    {showHtmlEditor ? (
                      <Textarea
                        id="resource-content-html"
                        className="min-h-44 font-mono text-xs"
                        value={editData.content_html}
                        onChange={(event) =>
                          setEditData((prev) => ({
                            ...prev,
                            content_html: event.target.value,
                          }))
                        }
                      />
                    ) : null}
                    {showHtmlPreview ? (
                      <div className="mt-3 space-y-2">
                        <Label className="text-muted-foreground">Live Preview</Label>
                        <div
                          className="prose prose-sm max-w-none rounded-md border bg-muted/20 p-3"
                          dangerouslySetInnerHTML={{
                            __html: editData.content_html || "<p>No content yet.</p>",
                          }}
                        />
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <div className="space-y-1.5">
                    <Label htmlFor="edit-resource-file">Replace File</Label>
                    <Input
                      id="edit-resource-file"
                      type="file"
                      onChange={(event) =>
                        setReplacementFile(event.target.files?.[0] ?? null)
                      }
                    />
                    {replacementFile ? (
                      <p className="text-xs text-muted-foreground">
                        New file: {replacementFile.name}
                      </p>
                    ) : (
                      <p className="text-xs text-muted-foreground">
                        Leave empty to keep the current file.
                      </p>
                    )}
                  </div>
                )}
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
                {resource.visibility_scope === "global" ? (
                  <span className="text-sm text-muted-foreground">
                    Global visibility
                  </span>
                ) : visibleRoleSlugs.length ? (
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
                <p className="text-xs text-muted-foreground">
                  {editData.visibility_mode === "role_based"
                    ? "Select one or more roles."
                    : "Ignored unless visibility is role-based."}
                </p>
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
              <Button onClick={handleSave} disabled={isPending || isReplacingFile}>
                <SaveIcon className="size-4 mr-1" />
                {isPending || isReplacingFile ? "Saving..." : "Save Changes"}
              </Button>
            </div>
          )}
        </div>
      </DrawerContent>
    </Drawer>
  );
}
