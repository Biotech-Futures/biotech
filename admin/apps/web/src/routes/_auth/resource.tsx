import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import {
  ResourceFilters,
  ResourceTable,
  ResourceDetailDrawer,
  ResourceUploadSheet,
  createResourceColumns,
} from "@/components/resource";
import {
  downloadResourceFile,
  useDeleteResource,
  useQueryResourceRoles,
  useQueryResourceTracks,
  useQueryResources,
  useUpdateResource,
} from "@/query/resource";
import type {
  Resource,
  ResourceOrder,
  ResourceTypeName,
} from "@/type/resource";
import { RESOURCE_TRACKS } from "@/type/resource";
import { Button } from "@/components/ui/button";
import { UploadIcon } from "lucide-react";

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
  const [batchRoleIds, setBatchRoleIds] = useState<number[]>([]);

  const [selectedResource, setSelectedResource] = useState<Resource | null>(
    null,
  );
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState<"view" | "edit">("view");
  const [uploadOpen, setUploadOpen] = useState(false);

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

  useEffect(() => {
    setPage(1);
  }, [search, uploader, trackId, order, resourceType]);

  useEffect(() => {
    if (!bulkMode) {
      setSelectedIds([]);
      setShowBatchVisibilityEditor(false);
      setBatchRoleIds([]);
    }
  }, [bulkMode]);

  const availableRoles = rolesData?.data.filter((role) => role.slug !== "admin") ?? [];

  const resources = useMemo(() => {
    const items = [...(data?.data.items ?? [])];
    const getSortTimestamp = (resource: Resource) => {
      const parsed = Date.parse(resource.uploaded_at ?? "");
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
          a.resource_name.localeCompare(b.resource_name),
      );
    }

    return items.sort(
      (a, b) =>
        getSortTimestamp(b) - getSortTimestamp(a) ||
        a.resource_name.localeCompare(b.resource_name),
    );
  }, [data?.data.items, order]);
  const totalPages = Math.max(
    1,
    Math.ceil((data?.data.total ?? 0) / (data?.data.limit ?? 10)),
  );

  const handleViewDetail = (resource: Resource) => {
    setSelectedResource(resource);
    setDrawerMode("view");
    setDrawerOpen(true);
  };

  const handleEdit = (resource: Resource) => {
    setSelectedResource(resource);
    setDrawerMode("edit");
    setDrawerOpen(true);
  };

  const handleDelete = (resource: Resource) => {
    const shouldDelete = window.confirm(
      `Delete resource "${resource.resource_name}"?`,
    );
    if (!shouldDelete) return;
    deleteResource(resource.id);
    setSelectedIds((prev) => prev.filter((id) => id !== resource.id));
  };

  const handleDownload = async (resource: Resource) => {
    if (!resource.file_name) {
      window.alert("This resource does not have an uploaded file.");
      return;
    }
    try {
      await downloadResourceFile(resource.id, resource.file_name);
    } catch {
      window.alert("Download failed. Please try again.");
    }
  };

  const columns = createResourceColumns({
    onViewDetail: handleViewDetail,
    onEdit: handleEdit,
    onDelete: handleDelete,
    onDownload: handleDownload,
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
    await Promise.all(
      selectedIds.map((id) =>
        updateResourceAsync({
          id,
          updates: { role_ids: batchRoleIds },
        }),
      ),
    );
    setSelectedIds([]);
    setShowBatchVisibilityEditor(false);
    setBatchRoleIds([]);
  };

  return (
    <div className="p-4 space-y-4">
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
        trackOptions={tracksData?.data?.length ? tracksData.data : RESOURCE_TRACKS}
        actionSlot={
          <div className="flex items-center gap-2">
            <Button
              variant={bulkMode ? "default" : "outline"}
              onClick={() => setBulkMode((prev) => !prev)}
            >
              {bulkMode ? "Exit Batch Mode" : "Batch Mode"}
            </Button>
            <Button onClick={() => setUploadOpen(true)}>
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
                if (!availableRoles.length) {
                  window.alert("No roles available.");
                  return;
                }
                setShowBatchVisibilityEditor((prev) => !prev);
              }}
            >
              Batch Set Visibility
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
            Set visibility roles for {selectedIds.length} selected resources
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
            <Button size="sm" onClick={handleBatchUpdateVisibility}>
              Apply Visibility
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setShowBatchVisibilityEditor(false);
                setBatchRoleIds([]);
              }}
            >
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

      <ResourceDetailDrawer
        resource={selectedResource}
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        mode={drawerMode}
        onSwitchToEdit={() => setDrawerMode("edit")}
        onDownload={handleDownload}
      />

      <ResourceUploadSheet open={uploadOpen} onOpenChange={setUploadOpen} />
    </div>
  );
}
