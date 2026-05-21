import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  SortableTableHead,
  useSortableRows,
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
import { labelizeTrack, labelizeUserRole, type UserAccount } from "@/type/user";
import { useCallback } from "react";

type UserSortKey = "name" | "email" | "role" | "track" | "status";

const initialUserSort: SortState<UserSortKey> = {
  key: "name",
  direction: "asc",
};

interface UserTableProps {
  data: UserAccount[];
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onView: (user: UserAccount) => void;
  onEdit: (user: UserAccount) => void;
  onToggleActive: (user: UserAccount) => void;
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
  isPending,
}: UserTableProps) {
  const getSortValue = useCallback((user: UserAccount, key: UserSortKey) => {
    switch (key) {
      case "name":
        return user.name;
      case "email":
        return user.email;
      case "role":
        return labelizeUserRole(user.role);
      case "track":
        return labelizeTrack(user.track);
      case "status":
        return user.active;
    }
  }, []);
  const { sortState, setSortState, sortedRows } = useSortableRows(
    data,
    initialUserSort,
    getSortValue,
  );

  return (
    <div className="space-y-4">
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>
                <SortableTableHead
                  label="Name"
                  sortKey="name"
                  sortState={sortState}
                  onSortChange={setSortState}
                />
              </TableHead>
              <TableHead>
                <SortableTableHead
                  label="Email"
                  sortKey="email"
                  sortState={sortState}
                  onSortChange={setSortState}
                />
              </TableHead>
              <TableHead>
                <SortableTableHead
                  label="Role"
                  sortKey="role"
                  sortState={sortState}
                  onSortChange={setSortState}
                />
              </TableHead>
              <TableHead>
                <SortableTableHead
                  label="Track"
                  sortKey="track"
                  sortState={sortState}
                  onSortChange={setSortState}
                />
              </TableHead>
              <TableHead>
                <SortableTableHead
                  label="Status"
                  sortKey="status"
                  sortState={sortState}
                  onSortChange={setSortState}
                />
              </TableHead>
              <TableHead>Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isPending ? (
              <TableRow>
                <TableCell colSpan={6} className="h-24 text-center">
                  Loading users...
                </TableCell>
              </TableRow>
            ) : data.length ? (
              sortedRows.map((user) => (
                <TableRow key={user.id}>
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
                  <TableCell>{labelizeTrack(user.track)}</TableCell>
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
                        onClick={() => onEdit(user)}
                      >
                        Edit
                      </Button>
                      <Button
                        variant={user.active ? "secondary" : "default"}
                        size="sm"
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
                <TableCell colSpan={6} className="h-24 text-center">
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
