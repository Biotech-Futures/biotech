import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import {
  ResourceFilters,
  ResourceTable,
  ResourceDetailDrawer,
  createResourceColumns,
} from "@/components/resource";
import { useDeleteResource, useQueryResources } from "@/query/resource";
import type { Resource, ResourceTypeName } from "@/type/resource";

export const Route = createFileRoute("/_auth/resource")({
  component: ResourcePage,
});

function ResourcePage() {
  const [search, setSearch] = useState("");
  const [type, setType] = useState<ResourceTypeName | undefined>();
  const [page, setPage] = useState(1);

  const [selectedResource, setSelectedResource] = useState<Resource | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState<"view" | "edit">("view");

  const { data, isPending } = useQueryResources({
    page,
    search,
    type,
  });

  const { mutate: deleteResource } = useDeleteResource();

  useEffect(() => {
    setPage(1);
  }, [search, type]);

  const resources = data?.data.items ?? [];
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
