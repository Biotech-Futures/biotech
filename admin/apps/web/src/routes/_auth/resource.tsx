import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import {
  ResourceFilters,
  ResourceTable,
  ResourceDetailDrawer,
  ResourceUploadSheet,
  createResourceColumns,
} from "@/components/resource";
import { downloadResourceFile, useDeleteResource, useQueryResources } from "@/query/resource";
import type { Resource, ResourceOrder, ResourceTypeName } from "@/type/resource";
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
  const [resourceType, setResourceType] = useState<ResourceTypeName | undefined>();
  const [page, setPage] = useState(1);

  const [selectedResource, setSelectedResource] = useState<Resource | null>(null);
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

  const { mutate: deleteResource } = useDeleteResource();

  useEffect(() => {
    setPage(1);
  }, [search, uploader, trackId, order, resourceType]);

  const resources = useMemo(() => {
    const items = [...(data?.data.items ?? [])];
    const getSortTimestamp = (resource: Resource) => {
      const parsed = Date.parse(resource.uploaded_at ?? "");
      if (!Number.isNaN(parsed)) return parsed;

      const idNumber = Number.parseInt(String(resource.id).replace(/\D/g, ""), 10);
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
  const totalPages = Math.max(1, Math.ceil((data?.data.total ?? 0) / (data?.data.limit ?? 10)));

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
    const shouldDelete = window.confirm(`Delete resource "${resource.resource_name}"?`);
    if (!shouldDelete) return;
    deleteResource(resource.id);
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

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Resource Management</h1>
          <p className="text-muted-foreground">
            View and maintain resource metadata, type, and role visibility
          </p>
        </div>
        <Button onClick={() => setUploadOpen(true)}>
          <UploadIcon className="size-4 mr-1" />
          Upload Resource
        </Button>
      </div>

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
      />

      <ResourceTable
        columns={columns}
        data={resources}
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
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
