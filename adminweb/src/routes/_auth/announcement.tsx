import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { BulkActionsBar } from "@/components/ui/bulk-actions-bar";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  SortableTableHead,
  type SortState,
} from "@/components/ui/sortable-table";
import { TablePaginationBar } from "@/components/ui/table-pagination";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { MoreHorizontal, Plus } from "lucide-react";
import {
  useListAnnouncements,
  useArchiveAnnouncement,
  useDeleteAnnouncement,
  useGetAnnouncement,
} from "@/query/announcement";
import { AnnouncementFormSheet } from "@/components/announcement/AnnouncementFormSheet";
import { AnnouncementDetailSheet } from "@/components/announcement/AnnouncementDetailSheet";
import type { Announcement, AnnouncementListItem } from "@/type/announcement";
import { toast } from "sonner";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

const DEFAULT_PAGE_SIZE = 25;

export const Route = createFileRoute("/_auth/announcement")({
  component: AnnouncementPage,
});

function scopeLabel(scope: string) {
  if (scope === "global") return "All users";
  if (scope === "role_based") return "By role";
  return scope;
}

type AnnouncementSortKey = "title" | "audience" | "published" | "status";

const initialAnnouncementSort: SortState<AnnouncementSortKey> = {
  key: "published",
  direction: "desc",
};

function AnnouncementPage() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [search, setSearch] = useState("");
  const [showArchived, setShowArchived] = useState(false);

  const [formOpen, setFormOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);

  const [detailOpen, setDetailOpen] = useState(false);
  const [detailId, setDetailId] = useState<number | null>(null);
  const [sortState, setSortState] = useState<SortState<AnnouncementSortKey>>(
    initialAnnouncementSort,
  );

  const { data, isPending } = useListAnnouncements(
    page,
    pageSize,
    search,
    showArchived ? true : false,
    sortState,
  );
  const { data: editingAnn } = useGetAnnouncement(editingId);
  const { mutateAsync: archive, isPending: isArchiving } =
    useArchiveAnnouncement();
  const { mutateAsync: deleteAnnouncement, isPending: isDeleting } =
    useDeleteAnnouncement();
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
  // Selected announcements, keyed by id, so the selection persists across pages
  // and we keep each row's archived state for the bulk-action counts.
  const [selected, setSelected] = useState<Map<number, AnnouncementListItem>>(
    new Map(),
  );

  const items = useMemo(() => data?.items ?? [], [data?.items]);
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const isBusy = isArchiving || isDeleting;

  // Keep selected snapshots in sync with refetched page data so status changes
  // (e.g. after a single archive) are reflected in the bulk-action counts.
  useEffect(() => {
    setSelected((prev) => {
      if (prev.size === 0) return prev;
      let changed = false;
      const next = new Map(prev);
      for (const item of items) {
        if (next.has(item.id) && next.get(item.id) !== item) {
          next.set(item.id, item);
          changed = true;
        }
      }
      return changed ? next : prev;
    });
  }, [items]);

  const clearSelection = useCallback(() => setSelected(new Map()), []);

  const selectedList = useMemo(() => [...selected.values()], [selected]);
  const archivableCount = useMemo(
    () => selectedList.filter((a) => !a.archivedAt).length,
    [selectedList],
  );

  const selectedOnPage = items.filter((item) => selected.has(item.id));
  const headerState: boolean | "indeterminate" =
    items.length > 0 && selectedOnPage.length === items.length
      ? true
      : selectedOnPage.length > 0
        ? "indeterminate"
        : false;

  const toggleRow = useCallback((item: AnnouncementListItem) => {
    setSelected((prev) => {
      const next = new Map(prev);
      if (next.has(item.id)) next.delete(item.id);
      else next.set(item.id, item);
      return next;
    });
  }, []);

  const toggleAllOnPage = useCallback(() => {
    setSelected((prev) => {
      const next = new Map(prev);
      const allSelected =
        items.length > 0 && items.every((i) => next.has(i.id));
      if (allSelected) {
        items.forEach((i) => next.delete(i.id));
      } else {
        items.forEach((i) => next.set(i.id, i));
      }
      return next;
    });
  }, [items]);

  function handlePageSizeChange(size: number) {
    setPageSize(size);
    setPage(1);
  }

  async function handleBulkArchive() {
    const targets = selectedList.filter((a) => !a.archivedAt);
    if (!targets.length) return;
    // Settle every archive independently so one failure doesn't strand the rest.
    const outcomes = await Promise.allSettled(
      targets.map((a) => archive(a.id).then(() => a.id)),
    );
    const doneIds = outcomes
      .filter(
        (o): o is PromiseFulfilledResult<number> => o.status === "fulfilled",
      )
      .map((o) => o.value);
    const failed = targets.length - doneIds.length;

    if (doneIds.length) {
      setSelected((prev) => {
        const next = new Map(prev);
        doneIds.forEach((id) => next.delete(id));
        return next;
      });
    }

    if (failed === 0) {
      toast.success(
        `Archived ${doneIds.length} announcement${doneIds.length === 1 ? "" : "s"}.`,
      );
    } else if (doneIds.length) {
      toast.error(
        `Archived ${doneIds.length}, but ${failed} could not be archived.`,
      );
    } else {
      toast.error("Unable to archive the selected announcements.");
    }
  }

  async function handleBulkDelete() {
    const targets = selectedList;
    if (!targets.length) {
      setBulkDeleteOpen(false);
      return;
    }
    // Settle every delete independently so one failure doesn't strand the rest.
    const outcomes = await Promise.allSettled(
      targets.map((a) => deleteAnnouncement(a.id).then(() => a.id)),
    );
    const doneIds = outcomes
      .filter(
        (o): o is PromiseFulfilledResult<number> => o.status === "fulfilled",
      )
      .map((o) => o.value);
    const failed = targets.length - doneIds.length;

    if (doneIds.length) {
      setSelected((prev) => {
        const next = new Map(prev);
        doneIds.forEach((id) => next.delete(id));
        return next;
      });
    }

    if (failed === 0) {
      toast.success(
        `Deleted ${doneIds.length} announcement${doneIds.length === 1 ? "" : "s"}.`,
      );
    } else if (doneIds.length) {
      toast.error(
        `Deleted ${doneIds.length}, but ${failed} could not be deleted.`,
      );
    } else {
      toast.error("Unable to delete the selected announcements.");
    }
    setBulkDeleteOpen(false);
  }

  function openCreate() {
    setEditingId(null);
    setFormOpen(true);
  }

  function openEdit(item: AnnouncementListItem) {
    setEditingId(item.id);
    setFormOpen(true);
  }

  function openDetail(id: number) {
    setDetailId(id);
    setDetailOpen(true);
  }

  async function handleArchive(id: number) {
    try {
      await archive(id);
      toast.success("Archived");
    } catch {
      toast.error("Failed to archive");
    }
  }

  async function handleDelete() {
    if (deleteId === null) return;
    try {
      await deleteAnnouncement(deleteId);
      toast.success("Announcement deleted");
    } catch {
      toast.error("Failed to delete");
    } finally {
      setDeleteId(null);
    }
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <span />
        <Button onClick={openCreate}>
          <Plus className="size-4 mr-1" />
          New Announcement
        </Button>
      </div>

      <div className="flex items-center gap-3">
        <Input
          placeholder="Search announcements..."
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
            setSelected(new Map());
          }}
          className="max-w-sm"
        />
        <Button
          variant={showArchived ? "default" : "outline"}
          size="sm"
          onClick={() => {
            setShowArchived((v) => !v);
            setPage(1);
            setSelected(new Map());
          }}
        >
          {showArchived ? "Show Active" : "Show Archived"}
        </Button>
      </div>

      {selected.size > 0 && (
        <BulkActionsBar
          count={selected.size}
          noun="announcement"
          onClear={clearSelection}
          disabled={isBusy}
        >
          <Button
            variant="outline"
            size="sm"
            onClick={handleBulkArchive}
            disabled={isBusy || archivableCount === 0}
          >
            Archive ({archivableCount})
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="text-destructive hover:text-destructive"
            onClick={() => setBulkDeleteOpen(true)}
            disabled={isBusy}
          >
            Delete
          </Button>
        </BulkActionsBar>
      )}

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10">
                <Checkbox
                  checked={headerState}
                  onCheckedChange={toggleAllOnPage}
                  aria-label="Select all on this page"
                  disabled={isPending || items.length === 0}
                />
              </TableHead>
              <TableHead>
                <SortableTableHead
                  label="Title"
                  sortKey="title"
                  sortState={sortState}
                  onSortChange={(nextSort) => {
                    setSortState(nextSort);
                    setPage(1);
                  }}
                />
              </TableHead>
              <TableHead>
                <SortableTableHead
                  label="Audience"
                  sortKey="audience"
                  sortState={sortState}
                  onSortChange={(nextSort) => {
                    setSortState(nextSort);
                    setPage(1);
                  }}
                />
              </TableHead>
              <TableHead>
                <SortableTableHead
                  label="Published"
                  sortKey="published"
                  sortState={sortState}
                  onSortChange={(nextSort) => {
                    setSortState(nextSort);
                    setPage(1);
                  }}
                />
              </TableHead>
              <TableHead>
                <SortableTableHead
                  label="Status"
                  sortKey="status"
                  sortState={sortState}
                  onSortChange={(nextSort) => {
                    setSortState(nextSort);
                    setPage(1);
                  }}
                />
              </TableHead>
              <TableHead className="w-10" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {isPending ? (
              <TableRow>
                <TableCell
                  colSpan={6}
                  className="h-24 text-center text-muted-foreground"
                >
                  Loading...
                </TableCell>
              </TableRow>
            ) : items.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={6}
                  className="h-24 text-center text-muted-foreground"
                >
                  No announcements found.
                </TableCell>
              </TableRow>
            ) : (
              items.map((item) => (
                <TableRow
                  key={item.id}
                  data-state={selected.has(item.id) ? "selected" : undefined}
                >
                  <TableCell
                    className="w-10"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Checkbox
                      checked={selected.has(item.id)}
                      onCheckedChange={() => toggleRow(item)}
                      aria-label={`Select ${item.title}`}
                    />
                  </TableCell>
                  <TableCell>
                    <button
                      className="font-medium text-left hover:underline"
                      onClick={() => openDetail(item.id)}
                    >
                      {item.title}
                    </button>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">
                      {scopeLabel(item.visibilityScope)}
                    </Badge>
                    {item.visibilityScope === "role_based" &&
                      item.audiences.length > 0 && (
                        <span className="ml-1 text-xs text-muted-foreground">
                          {item.audiences
                            .map((a) => a.roleName)
                            .filter(Boolean)
                            .join(", ")}
                        </span>
                      )}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {new Date(item.publishedAt).toLocaleDateString()}
                  </TableCell>
                  <TableCell>
                    {item.archivedAt ? (
                      <Badge variant="secondary">Archived</Badge>
                    ) : (
                      <Badge variant="default">Active</Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon">
                          <MoreHorizontal className="size-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => openDetail(item.id)}>
                          View
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => openEdit(item)}>
                          Edit
                        </DropdownMenuItem>
                        {!item.archivedAt && (
                          <DropdownMenuItem
                            onClick={() => handleArchive(item.id)}
                          >
                            Archive
                          </DropdownMenuItem>
                        )}
                        <DropdownMenuItem
                          className="text-destructive"
                          onClick={() => setDeleteId(item.id)}
                        >
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <TablePaginationBar
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
        pageSize={pageSize}
        onPageSizeChange={handlePageSizeChange}
        disabled={isPending}
      />

      <AnnouncementDetailSheet
        id={detailId}
        open={detailOpen}
        onOpenChange={setDetailOpen}
      />

      <AnnouncementFormSheet
        open={formOpen}
        onOpenChange={setFormOpen}
        editing={editingId && editingAnn ? (editingAnn as Announcement) : null}
      />

      <AlertDialog
        open={deleteId !== null}
        onOpenChange={(open) => !open && setDeleteId(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this announcement?</AlertDialogTitle>
            <AlertDialogDescription>
              This permanently removes the announcement and its delivery
              history. This can't be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={handleDelete}>
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={bulkDeleteOpen} onOpenChange={setBulkDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Delete {selected.size}{" "}
              {selected.size === 1 ? "announcement" : "announcements"}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              This permanently removes them and their delivery history. This
              can't be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={isDeleting}
              onClick={(event) => {
                event.preventDefault();
                void handleBulkDelete();
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
