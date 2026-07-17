import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { TablePaginationBar } from "@/components/ui/table-pagination";
import {
  SortableTableHead,
  type SortState,
} from "@/components/ui/sortable-table";
import { CheckCheckIcon, InfoIcon } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  labelizeCountry,
  labelizeState,
  labelizeUserRole,
  type UserAccount,
} from "@/type/user";

export type UserSortKey =
  | "name"
  | "email"
  | "role"
  | "country"
  | "state"
  | "status";

const COLUMN_COUNT = 8;

export interface UserTableSelection {
  /** Explicitly checked row ids (used when selectAllMatching is false). */
  selectedIds: Set<string>;
  /** True once the admin has expanded selection to the whole filtered set. */
  selectAllMatching: boolean;
  /** Rows unchecked while in selectAllMatching mode. */
  excludedIds: Set<string>;
  /** Total rows matching the current filters (across all pages). */
  total: number;
  onSelectionChange: (ids: Set<string>) => void;
  onExcludedChange: (ids: Set<string>) => void;
  onSelectAllMatching: () => void;
  onClear: () => void;
}

interface UserTableProps {
  data: UserAccount[];
  page: number;
  totalPages: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
  onView: (user: UserAccount) => void;
  onEdit: (user: UserAccount) => void;
  onToggleActive: (user: UserAccount) => void;
  selection: UserTableSelection;
  sortState: SortState<UserSortKey>;
  onSortChange: (sortState: SortState<UserSortKey>) => void;
  isPending?: boolean;
}

export function UserTable({
  data,
  page,
  totalPages,
  pageSize,
  onPageChange,
  onPageSizeChange,
  onView,
  onEdit,
  onToggleActive,
  selection,
  sortState,
  onSortChange,
  isPending,
}: UserTableProps) {
  const {
    selectedIds,
    selectAllMatching,
    excludedIds,
    total,
    onSelectionChange,
    onExcludedChange,
    onSelectAllMatching,
    onClear,
  } = selection;

  const pageIds = data.map((user) => user.id);
  const isRowSelected = (id: string) =>
    selectAllMatching ? !excludedIds.has(id) : selectedIds.has(id);
  const selectedOnPage = pageIds.filter(isRowSelected);
  const headerChecked: boolean | "indeterminate" =
    selectedOnPage.length === 0
      ? false
      : selectedOnPage.length === pageIds.length
        ? true
        : "indeterminate";

  const toggleAllOnPage = () => {
    if (selectAllMatching) {
      const next = new Set(excludedIds);
      if (selectedOnPage.length === pageIds.length) {
        // Whole page currently selected -> exclude it.
        pageIds.forEach((id) => next.add(id));
      } else {
        pageIds.forEach((id) => next.delete(id));
      }
      onExcludedChange(next);
      return;
    }

    const next = new Set(selectedIds);
    if (selectedOnPage.length === pageIds.length) {
      pageIds.forEach((id) => next.delete(id));
    } else {
      pageIds.forEach((id) => next.add(id));
    }
    onSelectionChange(next);
  };

  const toggleOne = (id: string) => {
    if (selectAllMatching) {
      const next = new Set(excludedIds);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      onExcludedChange(next);
      return;
    }

    const next = new Set(selectedIds);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    onSelectionChange(next);
  };

  const excludedCount = excludedIds.size;
  const effectiveAllCount = Math.max(0, total - excludedCount);
  const showExpandOffer =
    !selectAllMatching &&
    pageIds.length > 0 &&
    selectedOnPage.length === pageIds.length &&
    total > pageIds.length;
  const showSelectionBanner = !isPending && (showExpandOffer || selectAllMatching);

  return (
    <div className="space-y-4">
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10">
                <Checkbox
                  checked={headerChecked}
                  onCheckedChange={toggleAllOnPage}
                  disabled={isPending || pageIds.length === 0}
                  aria-label="Select all users on this page"
                />
              </TableHead>
              <TableHead>
                <SortableTableHead
                  label="Name"
                  sortKey="name"
                  sortState={sortState}
                  onSortChange={onSortChange}
                />
              </TableHead>
              <TableHead>
                <SortableTableHead
                  label="Email"
                  sortKey="email"
                  sortState={sortState}
                  onSortChange={onSortChange}
                />
              </TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Country</TableHead>
              <TableHead>State</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {showSelectionBanner && (
              <TableRow className="border-primary/20 bg-primary/10 hover:bg-primary/10">
                <TableCell
                  colSpan={COLUMN_COUNT}
                  className="py-3 text-center text-sm"
                >
                  {selectAllMatching ? (
                    <span className="inline-flex flex-wrap items-center justify-center gap-2">
                      <CheckCheckIcon
                        className="size-4 text-primary"
                        aria-hidden
                      />
                      <span aria-live="polite" className="font-medium">
                        {excludedCount > 0
                          ? `${effectiveAllCount} of ${total} users selected.`
                          : `All ${total} users matching these filters are selected.`}
                      </span>
                      <Button
                        variant="link"
                        size="sm"
                        className="h-auto p-0 font-semibold underline"
                        onClick={onClear}
                      >
                        Clear selection
                      </Button>
                    </span>
                  ) : (
                    <span className="inline-flex flex-wrap items-center justify-center gap-2">
                      <InfoIcon className="size-4 text-primary" aria-hidden />
                      <span className="font-medium">
                        All {pageIds.length} users on this page are selected.
                      </span>
                      <Button
                        variant="link"
                        size="sm"
                        className="h-auto p-0 font-semibold underline"
                        onClick={onSelectAllMatching}
                      >
                        Select all {total} users matching these filters
                      </Button>
                    </span>
                  )}
                </TableCell>
              </TableRow>
            )}
            {isPending ? (
              <TableRow>
                <TableCell colSpan={COLUMN_COUNT} className="h-24 text-center">
                  Loading users...
                </TableCell>
              </TableRow>
            ) : data.length ? (
              data.map((user) => (
                <TableRow
                  key={user.id}
                  data-state={isRowSelected(user.id) ? "selected" : undefined}
                >
                  <TableCell>
                    <Checkbox
                      checked={isRowSelected(user.id)}
                      onCheckedChange={() => toggleOne(user.id)}
                      aria-label={`Select ${user.name}`}
                    />
                  </TableCell>
                  <TableCell className="font-medium">
                    <button
                      type="button"
                      className="text-left transition hover:underline"
                      onClick={() => onView(user)}
                    >
                      {user.name}
                    </button>
                  </TableCell>
                  <TableCell>{user.email}</TableCell>
                  <TableCell>
                    {user.role ? (
                      <Badge variant="outline">
                        {labelizeUserRole(user.role)}
                      </Badge>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell>{labelizeCountry(user.country)}</TableCell>
                  <TableCell>{labelizeState(user.state)}</TableCell>
                  <TableCell>
                    <Badge variant={user.active ? "default" : "secondary"}>
                      {user.active ? "Active" : "Inactive"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        aria-label={`Edit ${user.name}`}
                        onClick={() => onEdit(user)}
                      >
                        Edit
                      </Button>
                      <Button
                        variant={user.active ? "secondary" : "default"}
                        size="sm"
                        aria-label={`${user.active ? "Deactivate" : "Activate"} ${user.name}`}
                        onClick={() => onToggleActive(user)}
                      >
                        {user.active ? "Deactivate" : "Activate"}
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={COLUMN_COUNT} className="h-24 text-center">
                  No users found.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <TablePaginationBar
        page={page}
        totalPages={totalPages}
        onPageChange={onPageChange}
        pageSize={pageSize}
        onPageSizeChange={onPageSizeChange}
        disabled={isPending}
      />
    </div>
  );
}
