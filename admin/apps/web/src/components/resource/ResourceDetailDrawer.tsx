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
    resource_kind: ResourceKind;
    track_id: number | null;
    resource_type: ResourceTypeName | null;
    content_html: string;
    role_ids: number[];
  }>({
    resource_name: "",
    resource_description: "",
    resource_kind: "file",
    track_id: null,
    resource_type: null,
    content_html: "",
    role_ids: [],
  });
  const [htmlFileName, setHtmlFileName] = useState("");
  const [showHtmlEditor, setShowHtmlEditor] = useState(true);
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
      resource_name: resource.resource_name,
      resource_description: resource.resource_description ?? "",
      resource_kind: resource.resource_kind,
      track_id: resource.track_id,
      resource_type: resource.resource_type,
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
    setShowHtmlEditor(true);
    setShowHtmlPreview(false);
  }, [resource]);

  if (!resource) return null;

  const handleSave = () => {
    const parsed = updateResourceSchema.safeParse({
      resource_name: editData.resource_name,
      resource_description: editData.resource_description,
      resource_kind: editData.resource_kind,
      track_id: editData.track_id,
      resource_type: editData.resource_type,
      content_html: editData.content_html || null,
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
            {mode === "view" ? resource.resource_name : "Edit Resource"}
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
                  <Label className="text-muted-foreground">Kind</Label>
                  <p>{resource.resource_kind === "page" ? "HTML Page" : "File"}</p>
                </div>
                <div>
                  <Label className="text-muted-foreground">Track</Label>
                  <p>{getResourceTrackLabel(resource.track_id)}</p>
                </div>
                {resource.resource_kind === "page" ? (
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
                  <Label htmlFor="resource-kind">Kind</Label>
                  <Select
                    value={editData.resource_kind}
                    onValueChange={(value) =>
                      setEditData((prev) => ({
                        ...prev,
                        resource_kind: value as ResourceKind,
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
                {editData.resource_kind === "page" ? (
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
                ) : null}
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
