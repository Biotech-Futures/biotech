import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import {
  ResourceFilters,
  ResourceTable,
  ResourceDialog,
  createResourceColumns,
} from "@/components/resource";
import {
  accessResourceFile,
  downloadResourceFile,
  openResourceAccess,
  useDeleteResource,
  useQueryResourceRoles,
  useQueryResourceTracks,
  useQueryResourceTypes,
  useQueryResources,
  useUpdateResource,
} from "@/query/resource";
import type {
  Resource,
  ResourceOrder,
  ResourceTypeName,
} from "@/type/resource";
import { Button } from "@/components/ui/button";
import { UploadIcon } from "lucide-react";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";

export const Route = createFileRoute("/_auth/resource")({
  component: ResourcePage,
});

function ResourcePage() {
  const [search, setSearch] = useState("");
  const [uploader, setUploader] = useState("");
  const [trackId, setTrackId] = useState<number | undefined>();
  const [order, setOrder] = useState<ResourceOrder>("newest");
  const [resourceType, setResourceType] = useState<
    ResourceTypeName | undefined
  >();
  const [page, setPage] = useState(1);
  const [bulkMode, setBulkMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [showBatchVisibilityEditor, setShowBatchVisibilityEditor] =
    useState(false);
  const [singleBatchEditor, setSingleBatchEditor] = useState<
    "visibility" | "track" | "roles" | null
  >(null);
  const [batchVisibilityScope, setBatchVisibilityScope] = useState<
    "track_based" | "role_based"
  >("role_based");
  const [batchTrackId, setBatchTrackId] = useState<number | null>(null);
  const [batchRoleIds, setBatchRoleIds] = useState<number[]>([]);

  const [selectedResource, setSelectedResource] = useState<Resource | null>(
    null,
  );
  const [resourceDialogOpen, setResourceDialogOpen] = useState(false);
  const [resourceDialogMode, setResourceDialogMode] = useState<
    "create" | "view" | "edit"
  >("view");

  const { data, isPending } = useQueryResources({
    page,
    search,
    uploader,
    track_id: trackId,
    order,
    resource_type: resourceType,
  });

  const { mutate: deleteResource, mutateAsync: deleteResourceAsync } = useDeleteResource();
  const { mutateAsync: updateResourceAsync } = useUpdateResource();
  const { data: rolesData } = useQueryResourceRoles();
  const { data: tracksData } = useQueryResourceTracks();
  const { data: typesData } = useQueryResourceTypes();

  useEffect(() => {
    setPage(1);
  }, [search, uploader, trackId, order, resourceType]);

  useEffect(() => {
    if (!bulkMode) {
      setSelectedIds([]);
      setShowBatchVisibilityEditor(false);
      setSingleBatchEditor(null);
      setBatchVisibilityScope("role_based");
      setBatchTrackId(null);
      setBatchRoleIds([]);
    }
  }, [bulkMode]);

  const availableRoles = rolesData?.data.filter((role) => role.slug !== "admin") ?? [];

  const resources = useMemo(() => {
    const items = [...(data?.data.items ?? [])];

    const getSortTimestamp = (resource: Resource) => {
      const raw = resource.uploaded_at ?? "";
      let normalized = raw.includes("T") ? raw : raw.replace(" ", "T");
      normalized = normalized
        .replace(/([+-]\d{2})$/, "$1:00")
        .replace(/([+-]\d{2})(\d{2})$/, "$1:$2");
      const hasTimezone = /(?:Z|[+-]\d{2}:\d{2})$/i.test(normalized);
      const parsed = Date.parse(hasTimezone ? normalized : `${normalized}Z`);
      if (!Number.isNaN(parsed)) return parsed;

      const idNumber = Number.parseInt(
        String(resource.id).replace(/\D/g, ""),
        10,
      );
      if (!Number.isNaN(idNumber)) return idNumber;

      return 0;
    };

    if (order === "oldest") {
      return items.sort(
        (a, b) =>
          getSortTimestamp(a) - getSortTimestamp(b) ||
          a.name.localeCompare(b.name),
      );
    }

    return items.sort(
      (a, b) =>
        getSortTimestamp(b) - getSortTimestamp(a) ||
        a.name.localeCompare(b.name),
    );
  }, [data?.data.items, order]);
  const totalPages = Math.max(
    1,
    Math.ceil((data?.data.total ?? 0) / (data?.data.limit ?? 10)),
  );

  const handleViewDetail = (resource: Resource) => {
    setSelectedResource(resource);
    setResourceDialogMode("view");
    setResourceDialogOpen(true);
  };

  const handleEdit = (resource: Resource) => {
    setSelectedResource(resource);
    setResourceDialogMode("edit");
    setResourceDialogOpen(true);
  };

  const handleDelete = (resource: Resource) => {
    const shouldDelete = window.confirm(
      `Delete resource "${resource.name}"?`,
    );
    if (!shouldDelete) return;
    deleteResource(resource.id);
    setSelectedIds((prev) => prev.filter((id) => id !== resource.id));
  };

  const handleDownload = async (resource: Resource) => {
    if (!resource.file_name) {
      toast.error("This resource does not have an uploaded file.");
      return;
    }
    try {
      await downloadResourceFile(resource.id, resource.file_name);
    } catch {
      toast.error("Download failed. Please try again.");
    }
  };

  const handleAccess = async (resource: Resource) => {
    if (!resource.file_name) {
      toast.error("This resource does not have an uploaded file.");
      return;
    }
    try {
      const access = await accessResourceFile(resource.id);
      openResourceAccess(access);
    } catch {
      toast.error("Resource access failed. Please try again.");
    }
  };

  const columns = createResourceColumns({
    onViewDetail: handleViewDetail,
    onEdit: handleEdit,
    onDelete: handleDelete,
    onAccess: handleAccess,
    onDownload: handleDownload,
    trackOptions: tracksData?.data ?? [],
  });

  const handleBatchDelete = async () => {
    if (!selectedIds.length) return;
    const shouldDelete = window.confirm(`Delete ${selectedIds.length} selected resources?`);
    if (!shouldDelete) return;

    await Promise.all(selectedIds.map((id) => deleteResourceAsync(id)));
    setSelectedIds([]);
  };

  const handleBatchUpdateVisibility = async () => {
    if (!selectedIds.length) return;

    if (batchVisibilityScope === "role_based" && !batchRoleIds.length) {
      toast.error("Please select at least one role for role-based visibility.");
      return;
    }

    if (batchVisibilityScope === "track_based" && batchTrackId === null) {
      toast.error("Please select a track for track-based visibility.");
      return;
    }

    await Promise.all(
      selectedIds.map((id) =>
        updateResourceAsync({
          id,
          updates: {
            visibility_scope: batchVisibilityScope,
            track_id: batchTrackId,
            role_ids: batchRoleIds,
          },
        }),
      ),
    );
    setSelectedIds([]);
    setShowBatchVisibilityEditor(false);
    setSingleBatchEditor(null);
    setBatchVisibilityScope("role_based");
    setBatchTrackId(null);
    setBatchRoleIds([]);
  };

  const handleBatchApplyVisibilityOnly = async () => {
    if (!selectedIds.length) return;
    await Promise.all(
      selectedIds.map((id) =>
        updateResourceAsync({
          id,
          updates: {
            visibility_scope: batchVisibilityScope,
          },
        }),
      ),
    );
    setSelectedIds([]);
    setShowBatchVisibilityEditor(false);
    setSingleBatchEditor(null);
  };

  const handleBatchApplyTrackOnly = async () => {
    if (!selectedIds.length) return;
    if (batchTrackId === null) {
      toast.error("Please select a track.");
      return;
    }
    await Promise.all(
      selectedIds.map((id) =>
        updateResourceAsync({
          id,
          updates: {
            track_id: batchTrackId,
          },
        }),
      ),
    );
    setSelectedIds([]);
    setShowBatchVisibilityEditor(false);
    setSingleBatchEditor(null);
  };

  const handleBatchApplyRolesOnly = async () => {
    if (!selectedIds.length) return;
    if (!batchRoleIds.length) {
      toast.error("Please select at least one role.");
      return;
    }
    await Promise.all(
      selectedIds.map((id) =>
        updateResourceAsync({
          id,
          updates: {
            role_ids: batchRoleIds,
          },
        }),
      ),
    );
    setSelectedIds([]);
    setShowBatchVisibilityEditor(false);
    setSingleBatchEditor(null);
  };

  return (
    <div className="min-w-0 p-4 space-y-4">
      <ResourceFilters
        search={search}
        onSearchChange={setSearch}
        uploader={uploader}
        onUploaderChange={setUploader}
        trackId={trackId}
        onTrackIdChange={setTrackId}
        order={order}
        onOrderChange={setOrder}
        type={resourceType}
        onTypeChange={setResourceType}
        trackOptions={tracksData?.data ?? []}
        typeOptions={typesData?.data}
        actionSlot={
          <div className="flex w-full flex-wrap items-center justify-start gap-2 xl:justify-end">
            <Button
              type="button"
              variant={bulkMode ? "default" : "outline"}
              onClick={() => setBulkMode((prev) => !prev)}
            >
              {bulkMode ? "Exit Batch Mode" : "Batch Mode"}
            </Button>
            <Button
              type="button"
              onClick={() => {
                setSelectedResource(null);
                setResourceDialogMode("create");
                setResourceDialogOpen(true);
              }}
            >
              <UploadIcon className="size-4 mr-1" />
              Upload Resource
            </Button>
          </div>
        }
      />

      {bulkMode && selectedIds.length ? (
        <div className="flex items-center justify-between rounded-md border bg-muted/30 px-3 py-2">
          <p className="text-sm text-muted-foreground">
            {selectedIds.length} selected
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setSingleBatchEditor(null);
                setShowBatchVisibilityEditor((prev) => !prev);
              }}
            >
              Batch Edit Access
            </Button>
            <Button
              variant={singleBatchEditor === "visibility" ? "default" : "outline"}
              size="sm"
              onClick={() => {
                setShowBatchVisibilityEditor(false);
                setSingleBatchEditor((prev) =>
                  prev === "visibility" ? null : "visibility",
                );
              }}
            >
              Visibility Only
            </Button>
            <Button
              variant={singleBatchEditor === "track" ? "default" : "outline"}
              size="sm"
              onClick={() => {
                setShowBatchVisibilityEditor(false);
                setSingleBatchEditor((prev) => (prev === "track" ? null : "track"));
              }}
            >
              Track Only
            </Button>
            <Button
              variant={singleBatchEditor === "roles" ? "default" : "outline"}
              size="sm"
              onClick={() => {
                setShowBatchVisibilityEditor(false);
                setSingleBatchEditor((prev) => (prev === "roles" ? null : "roles"));
              }}
            >
              Roles Only
            </Button>
            <Button variant="destructive" size="sm" onClick={handleBatchDelete}>
              Batch Delete
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setSelectedIds([])}>
              Clear Selection
            </Button>
          </div>
        </div>
      ) : null}
      {bulkMode && selectedIds.length && showBatchVisibilityEditor ? (
        <div className="rounded-md border bg-background px-3 py-3 space-y-3">
          <p className="text-sm text-muted-foreground">
            Batch update visibility, track, and roles for {selectedIds.length} selected resources
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="batch-visibility">Visibility</Label>
              <Select
                value={batchVisibilityScope}
                onValueChange={(value) =>
                  setBatchVisibilityScope(value as "track_based" | "role_based")
                }
              >
                <SelectTrigger id="batch-visibility">
                  <SelectValue placeholder="Select visibility" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="track_based">track_based</SelectItem>
                  <SelectItem value="role_based">role_based</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="batch-track">Track</Label>
              <Select
                value={batchTrackId === null ? undefined : String(batchTrackId)}
                onValueChange={(value) =>
                  setBatchTrackId(Number(value))
                }
              >
                <SelectTrigger id="batch-track">
                  <SelectValue placeholder="Select track" />
                </SelectTrigger>
                <SelectContent>
                  {(tracksData?.data ?? []).map((track) => (
                    <SelectItem key={track.id} value={String(track.id)}>
                      {track.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-4">
            {availableRoles.map((role) => {
              const checked = batchRoleIds.includes(role.id);
              return (
                <label key={role.id} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={(event) => {
                      const isChecked = event.target.checked;
                      setBatchRoleIds((prev) =>
                        isChecked
                          ? [...prev, role.id]
                          : prev.filter((id) => id !== role.id),
                      );
                    }}
                  />
                  <span>{role.slug}</span>
                </label>
              );
            })}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" onClick={handleBatchUpdateVisibility}>
              Apply Batch Changes
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setShowBatchVisibilityEditor(false);
                setSingleBatchEditor(null);
                setBatchVisibilityScope("role_based");
                setBatchTrackId(null);
                setBatchRoleIds([]);
              }}
            >
              Cancel
            </Button>
          </div>
        </div>
      ) : null}

      {bulkMode && selectedIds.length && singleBatchEditor === "visibility" ? (
        <div className="rounded-md border bg-background px-3 py-3 space-y-3">
          <p className="text-sm text-muted-foreground">
            Update visibility only for {selectedIds.length} selected resources
          </p>
          <div className="space-y-1.5 max-w-sm">
            <Label htmlFor="single-batch-visibility">Visibility</Label>
            <Select
              value={batchVisibilityScope}
              onValueChange={(value) =>
                setBatchVisibilityScope(value as "track_based" | "role_based")
              }
            >
              <SelectTrigger id="single-batch-visibility">
                <SelectValue placeholder="Select visibility" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="track_based">track_based</SelectItem>
                <SelectItem value="role_based">role_based</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={handleBatchApplyVisibilityOnly}>
              Apply Visibility Only
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setSingleBatchEditor(null)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : null}

      {bulkMode && selectedIds.length && singleBatchEditor === "track" ? (
        <div className="rounded-md border bg-background px-3 py-3 space-y-3">
          <p className="text-sm text-muted-foreground">
            Update track only for {selectedIds.length} selected resources
          </p>
          <div className="space-y-1.5 max-w-sm">
            <Label htmlFor="single-batch-track">Track</Label>
            <Select
              value={batchTrackId === null ? undefined : String(batchTrackId)}
              onValueChange={(value) =>
                setBatchTrackId(Number(value))
              }
            >
              <SelectTrigger id="single-batch-track">
                <SelectValue placeholder="Select track" />
              </SelectTrigger>
              <SelectContent>
                {(tracksData?.data ?? []).map((track) => (
                  <SelectItem key={track.id} value={String(track.id)}>
                    {track.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={handleBatchApplyTrackOnly}>
              Apply Track Only
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setSingleBatchEditor(null)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : null}

      {bulkMode && selectedIds.length && singleBatchEditor === "roles" ? (
        <div className="rounded-md border bg-background px-3 py-3 space-y-3">
          <p className="text-sm text-muted-foreground">
            Update roles only for {selectedIds.length} selected resources
          </p>
          <div className="flex flex-wrap items-center gap-4">
            {availableRoles.map((role) => {
              const checked = batchRoleIds.includes(role.id);
              return (
                <label key={role.id} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={(event) => {
                      const isChecked = event.target.checked;
                      setBatchRoleIds((prev) =>
                        isChecked
                          ? [...prev, role.id]
                          : prev.filter((id) => id !== role.id),
                      );
                    }}
                  />
                  <span>{role.slug}</span>
                </label>
              );
            })}
          </div>
          <div className="flex items-center gap-2">
            <Button size="sm" onClick={handleBatchApplyRolesOnly}>
              Apply Roles Only
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setSingleBatchEditor(null)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : null}

      <ResourceTable
        columns={columns}
        data={resources}
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
        bulkMode={bulkMode}
        selectedIds={selectedIds}
        onSelectedIdsChange={setSelectedIds}
        isPending={isPending}
      />

      <ResourceDialog
        resource={selectedResource}
        open={resourceDialogOpen}
        onOpenChange={setResourceDialogOpen}
        mode={resourceDialogMode}
        onModeChange={setResourceDialogMode}
        onDownload={handleDownload}
      />
    </div>
  );
}
