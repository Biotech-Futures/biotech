import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  SortableTableHead,
  type SortState,
} from "@/components/ui/sortable-table";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { labelizeState, labelizeUserRole, type UserAccount } from "@/type/user";

export type UserSortKey = "name" | "email" | "role" | "state" | "status";

interface UserTableProps {
  data: UserAccount[];
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onView: (user: UserAccount) => void;
  onEdit: (user: UserAccount) => void;
  onToggleActive: (user: UserAccount) => void;
  selectedIds: Set<string>;
  onSelectionChange: (ids: Set<string>) => void;
  sortState: SortState<UserSortKey>;
  onSortChange: (sortState: SortState<UserSortKey>) => void;
  isPending?: boolean;
}

export function UserTable({
  data,
  page,
  totalPages,
  onPageChange,
  onView,
  onEdit,
  onToggleActive,
  selectedIds,
  onSelectionChange,
  sortState,
  onSortChange,
  isPending,
}: UserTableProps) {
  const pageIds = data.map((user) => user.id);
  const selectedOnPage = pageIds.filter((id) => selectedIds.has(id));
  const headerChecked: boolean | "indeterminate" =
    selectedOnPage.length === 0
      ? false
      : selectedOnPage.length === pageIds.length
        ? true
        : "indeterminate";

  const toggleAllOnPage = () => {
    const next = new Set(selectedIds);
    if (selectedOnPage.length === pageIds.length) {
      pageIds.forEach((id) => next.delete(id));
    } else {
      pageIds.forEach((id) => next.add(id));
    }
    onSelectionChange(next);
  };

  const toggleOne = (id: string) => {
    const next = new Set(selectedIds);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    onSelectionChange(next);
  };

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
              <TableHead>State</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isPending ? (
              <TableRow>
                <TableCell colSpan={7} className="h-24 text-center">
                  Loading users...
                </TableCell>
              </TableRow>
            ) : data.length ? (
              data.map((user) => (
                <TableRow
                  key={user.id}
                  data-state={selectedIds.has(user.id) ? "selected" : undefined}
                >
                  <TableCell>
                    <Checkbox
                      checked={selectedIds.has(user.id)}
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
                <TableCell colSpan={7} className="h-24 text-center">
                  No users found.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Page {page} of {totalPages}
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1 || isPending}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages || isPending}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
