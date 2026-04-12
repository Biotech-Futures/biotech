import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import {
  ResourceFilters,
  ResourceTable,
  ResourceDetailDrawer,
  createResourceColumns,
} from "@/components/resource";
import { useDeleteResource, useQueryResources } from "@/query/resource";
import type { Resource, ResourceOrder, ResourceTypeName } from "@/type/resource";

export const Route = createFileRoute("/_auth/resource")({
  component: ResourcePage,
});

function ResourcePage() {
  const [search, setSearch] = useState("");
  const [uploader, setUploader] = useState("");
  const [order, setOrder] = useState<ResourceOrder>("newest");
  const [type, setType] = useState<ResourceTypeName | undefined>();
  const [page, setPage] = useState(1);

  const [selectedResource, setSelectedResource] = useState<Resource | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState<"view" | "edit">("view");

  const { data, isPending } = useQueryResources({
    page,
    search,
    uploader,
    order,
    type,
  });

  const { mutate: deleteResource } = useDeleteResource();

  useEffect(() => {
    setPage(1);
  }, [search, uploader, order, type]);

  const resources = useMemo(() => {
    const items = [...(data?.data.items ?? [])];
    const getSortTimestamp = (resource: Resource) => {
      const parsed = Date.parse(resource.upload_datetime ?? "");
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

  const columns = createResourceColumns({
    onViewDetail: handleViewDetail,
    onEdit: handleEdit,
    onDelete: handleDelete,
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
      </div>

      <ResourceFilters
        search={search}
        onSearchChange={setSearch}
        uploader={uploader}
        onUploaderChange={setUploader}
        order={order}
        onOrderChange={setOrder}
        type={type}
        onTypeChange={setType}
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
      />
    </div>
  );
}
