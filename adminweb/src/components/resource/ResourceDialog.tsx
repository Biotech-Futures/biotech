import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { FileTextIcon, SaveIcon, UploadIcon, XIcon } from "lucide-react";
import { toast } from "sonner";
import {
  useCreateResource,
  useQueryResource,
  useQueryResourceRoles,
  useQueryResourceTracks,
  useQueryResourceTypes,
  useReplaceResourceFile,
  useUpdateResource,
  useUploadResource,
} from "@/query/resource";
import { createResourceSchema, updateResourceSchema } from "@/schema/resource";
import type { Resource, VisibilityScope } from "@/type/resource";
import {
  ResourceFormFields,
  type ResourceFormData,
} from "./ResourceFormFields";
import { ResourceReadOnlyDetails } from "./ResourceReadOnlyDetails";

export type ResourceDialogMode = "create" | "view" | "edit";

interface ResourceDialogProps {
  resource: Resource | null;
  open: boolean;
  mode: ResourceDialogMode;
  onOpenChange: (open: boolean) => void;
  onModeChange: (mode: ResourceDialogMode) => void;
  onDownload?: (resource: Resource) => void;
}

const emptyFormData: ResourceFormData = {
  name: "",
  description: "",
  kind: "file",
  visibilityScope: "role_based",
  trackId: null,
  typeName: null,
  contentHtml: "",
  roleIds: [],
  labelInput: "",
};

function getErrorMessage(error: unknown) {
  if (
    typeof error === "object" &&
    error !== null &&
    "response" in error &&
    typeof (error as { response?: unknown }).response === "object" &&
    (error as { response?: { data?: unknown } }).response?.data &&
    typeof (error as { response?: { data?: { msg?: unknown } } }).response?.data
      ?.msg === "string"
  ) {
    return (
      (error as { response?: { data?: { msg?: string } } }).response?.data
        ?.msg ?? "Request failed."
    );
  }

  if (error instanceof Error) return error.message;
  return "Request failed. Please try again.";
}

function getInitialFormData(resource: Resource | null): ResourceFormData {
  if (!resource) return emptyFormData;

  const visibilityScope =
    resource.visibility_scope === "track_based" ||
    resource.visibility_scope === "role_based"
      ? resource.visibility_scope
      : resource.audiences.some((audience) => audience.role?.slug !== "admin")
        ? "role_based"
        : resource.track_id !== null
          ? "track_based"
          : "role_based";

  return {
    name: resource.name,
    description: resource.description ?? "",
    kind: resource.kind,
    visibilityScope: visibilityScope as VisibilityScope,
    trackId: resource.track_id,
    typeName: resource.type_name,
    contentHtml: resource.content_html ?? "",
    roleIds: Array.from(
      new Set(
        resource.audiences
          .filter(
            (audience) =>
              audience.role_id !== null && audience.role?.slug !== "admin",
          )
          .map((audience) => audience.role_id as number),
      ),
    ),
    labelInput: (resource.labels ?? []).map((l) => l.name).join(", "),
  };
}

export function ResourceDialog({
  resource,
  open,
  mode,
  onOpenChange,
  onModeChange,
  onDownload,
}: ResourceDialogProps) {
  const { data: detailData } = useQueryResource(resource?.id ?? null);
  const { data: rolesData } = useQueryResourceRoles();
  const { data: tracksData } = useQueryResourceTracks();
  const { data: typesData } = useQueryResourceTypes();
  const { mutateAsync: uploadResourceAsync, isPending: isUploadPending } =
    useUploadResource();
  const { mutateAsync: createResourceAsync, isPending: isCreatePending } =
    useCreateResource();
  const { mutateAsync: updateResourceAsync, isPending: isUpdatePending } =
    useUpdateResource();
  const { mutateAsync: replaceResourceFileAsync, isPending: isReplacingFile } =
    useReplaceResourceFile();

  const currentResource = detailData?.data ?? resource;
  const roles = rolesData?.data ?? [];
  const tracks = tracksData?.data ?? [];
  const types = typesData?.data ?? [];
  const isSaving =
    isUploadPending || isCreatePending || isUpdatePending || isReplacingFile;
  const isFormMode = mode === "create" || mode === "edit";

  const [formData, setFormData] = useState<ResourceFormData>(emptyFormData);
  const [file, setFile] = useState<File | null>(null);

  useEffect(() => {
    if (!open) return;
    setFormData(
      mode === "create" ? emptyFormData : getInitialFormData(currentResource),
    );
    setFile(null);
  }, [currentResource, mode, open]);

  const closeDialog = () => {
    onOpenChange(false);
  };

  const validateForm = () => {
    const name = formData.name.trim();
    const description = formData.description.trim();

    if (!name) {
      toast.error("Resource name is required.");
      return null;
    }

    if (!description) {
      toast.error("Resource description is required.");
      return null;
    }

    if (
      formData.visibilityScope === "track_based" &&
      formData.trackId === null
    ) {
      toast.error("Track is required for track-based visibility.");
      return null;
    }

    if (formData.visibilityScope === "role_based" && !formData.roleIds.length) {
      toast.error("Please select at least one role for role-based visibility.");
      return null;
    }

    if (formData.kind === "page" && !formData.contentHtml.trim()) {
      toast.error("HTML content is required for page resources.");
      return null;
    }

    const label_names = formData.labelInput
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    return {
      resource_name: name,
      resource_description: description,
      resource_kind: formData.kind,
      visibility_scope: formData.visibilityScope,
      resource_type: formData.typeName,
      content_html:
        formData.kind === "page" ? formData.contentHtml.trim() : null,
      track_id: formData.trackId,
      role_ids: formData.roleIds,
      label_names,
    };
  };

  const handleCreate = async () => {
    const values = validateForm();
    if (!values) return;

    if (formData.kind === "page") {
      const parsed = createResourceSchema.safeParse({
        ...values,
        resource_type: values.resource_type ?? "guide",
        track_id: values.track_id ?? undefined,
      });
      if (!parsed.success) {
        toast.error(parsed.error.issues[0]?.message ?? "Invalid form data.");
        return;
      }

      await createResourceAsync(parsed.data);
      closeDialog();
      return;
    }

    if (!file) {
      toast.error("Please choose a file first.");
      return;
    }

    const form = new FormData();
    form.append("file", file);
    form.append("resource_name", values.resource_name);
    form.append("resource_description", values.resource_description);
    form.append("visibility_scope", values.visibility_scope);
    if (values.resource_type)
      form.append("resource_type", values.resource_type);
    if (values.track_id !== null)
      form.append("track_id", String(values.track_id));
    values.role_ids.forEach((roleId) =>
      form.append("role_ids", String(roleId)),
    );
    values.label_names?.forEach((name) =>
      form.append("label_names", name),
    );

    await uploadResourceAsync(form);
    closeDialog();
  };

  const handleUpdate = async () => {
    if (!currentResource) return;

    const values = validateForm();
    if (!values) return;

    const parsed = updateResourceSchema.safeParse(values);
    if (!parsed.success) {
      toast.error(parsed.error.issues[0]?.message ?? "Invalid form data.");
      return;
    }

    await updateResourceAsync({
      id: currentResource.id,
      updates: parsed.data,
    });

    if (file && formData.kind !== "page") {
      const form = new FormData();
      form.append("file", file);
      await replaceResourceFileAsync({ id: currentResource.id, payload: form });
    }

    closeDialog();
  };

  const handleSubmit = async () => {
    try {
      if (mode === "create") {
        await handleCreate();
      } else if (mode === "edit") {
        await handleUpdate();
      }
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  };

  const title =
    mode === "create"
      ? "Upload Resource"
      : mode === "edit"
        ? "Edit Resource"
        : (currentResource?.name ?? "Resource Details");

  if (mode !== "create" && !currentResource) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[92vh] w-[95vw] max-w-[calc(100%-2rem)] flex-col gap-0 overflow-hidden p-0 sm:max-w-3xl">
        <DialogHeader className="shrink-0 border-b px-6 py-4 pr-12">
          <DialogTitle className="flex items-center gap-2">
            <FileTextIcon className="size-5" />
            {title}
          </DialogTitle>
        </DialogHeader>

        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain space-y-6 p-4 pb-24">
          {isFormMode ? (
            <ResourceFormFields
              value={formData}
              onChange={setFormData}
              roles={roles}
              tracks={tracks}
              types={types}
              file={file}
              onFileChange={setFile}
              fileLabel={mode === "create" ? "File" : "Replace File"}
              editorKey={currentResource?.id ?? "new-resource"}
              showAttachmentKind={mode === "edit"}
              canChangeKind={mode === "create"}
            />
          ) : currentResource ? (
            <ResourceReadOnlyDetails
              resource={currentResource}
              roles={roles}
              trackOptions={tracks}
              onDownload={onDownload}
            />
          ) : null}

          {currentResource ? (
            <>
              <Separator />
              <div className="grid gap-2 sm:grid-cols-[9rem_minmax(0,1fr)] sm:items-start">
                <Label className="pt-0.5 text-sm font-medium text-muted-foreground">
                  Uploader
                </Label>
                <div className="p-3 rounded-md bg-muted/50">
                  <p className="font-medium">
                    {`${currentResource.uploader.first_name} ${currentResource.uploader.last_name}`.trim()}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {currentResource.uploader.email}
                  </p>
                </div>
              </div>
            </>
          ) : null}
        </div>

        <DialogFooter className="mx-0 mb-0 shrink-0 rounded-none border-t px-4 py-4">
          {mode === "view" ? (
            <Button type="button" onClick={() => onModeChange("edit")}>
              Edit Resource
            </Button>
          ) : (
            <>
              <Button type="button" variant="outline" onClick={closeDialog}>
                <XIcon className="size-4 mr-1" />
                Cancel
              </Button>
              <Button type="button" onClick={handleSubmit} disabled={isSaving}>
                {mode === "create" ? (
                  <UploadIcon className="size-4 mr-1" />
                ) : (
                  <SaveIcon className="size-4 mr-1" />
                )}
                {isSaving
                  ? "Saving..."
                  : mode === "create"
                    ? formData.kind === "page"
                      ? "Create Page"
                      : "Upload"
                    : "Save Changes"}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
