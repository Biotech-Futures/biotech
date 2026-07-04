import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
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

export const Route = createFileRoute("/_auth/announcement")({
  component: AnnouncementPage,
});

function scopeLabel(scope: string) {
  if (scope === "global") return "All users";
  if (scope === "track_based") return "By track";
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
    search,
    showArchived ? true : false,
    sortState,
  );
  const { data: editingAnn } = useGetAnnouncement(editingId);
  const { mutateAsync: archive } = useArchiveAnnouncement();
  const { mutateAsync: deleteAnnouncement } = useDeleteAnnouncement();
  const [deleteId, setDeleteId] = useState<number | null>(null);

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / 10);

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
          }}
          className="max-w-sm"
        />
        <Button
          variant={showArchived ? "default" : "outline"}
          size="sm"
          onClick={() => {
            setShowArchived((v) => !v);
            setPage(1);
          }}
        >
          {showArchived ? "Show Active" : "Show Archived"}
        </Button>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
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
                  colSpan={5}
                  className="h-24 text-center text-muted-foreground"
                >
                  Loading...
                </TableCell>
              </TableRow>
            ) : items.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={5}
                  className="h-24 text-center text-muted-foreground"
                >
                  No announcements found.
                </TableCell>
              </TableRow>
            ) : (
              items.map((item) => (
                <TableRow key={item.id}>
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
                    {item.trackName && (
                      <span className="ml-1 text-xs text-muted-foreground">
                        {item.trackName}
                      </span>
                    )}
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

      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          {total} announcement{total !== 1 ? "s" : ""}
        </span>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      </div>

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
    </div>
  );
}
