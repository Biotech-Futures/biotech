import type { IndividualStudent } from "@/schema/match";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
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
  useSortableRows,
  type SortState,
} from "@/components/ui/sortable-table";
import { useCallback } from "react";

type IndividualStudentTableProps = {
  students: IndividualStudent[];
  isLoading?: boolean;
};

type IndividualStudentSortKey =
  | "index"
  | "name"
  | "track"
  | "trackId"
  | "interest"
  | "yearLevel";

const initialIndividualStudentSort: SortState<IndividualStudentSortKey> = {
  key: "name",
  direction: "asc",
};

function StudentTableSkeleton() {
  return (
    <>
      {Array.from({ length: 5 }).map((_, rowIndex) => (
        <TableRow key={rowIndex}>
          {Array.from({ length: 6 }).map((__, cellIndex) => (
            <TableCell key={cellIndex}>
              <Skeleton className="h-4 w-full max-w-[140px]" />
            </TableCell>
          ))}
        </TableRow>
      ))}
    </>
  );
}

export function IndividualStudentTable({
  students,
  isLoading,
}: IndividualStudentTableProps) {
  const getSortValue = useCallback(
    (student: IndividualStudent, key: IndividualStudentSortKey) => {
      switch (key) {
        case "index":
          return students.findIndex((item) => item.userId === student.userId);
        case "name":
          return `${student.firstName} ${student.lastName}`;
        case "track":
          return student.trackCode;
        case "trackId":
          return student.trackId;
        case "interest":
          return student.interests.join(", ");
        case "yearLevel":
          return student.yearLevel ?? 0;
      }
    },
    [students],
  );
  const { sortState, setSortState, sortedRows } = useSortableRows(
    students,
    initialIndividualStudentSort,
    getSortValue,
  );

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>
              <SortableTableHead
                label="#"
                sortKey="index"
                sortState={sortState}
                onSortChange={setSortState}
              />
            </TableHead>
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
                label="Track"
                sortKey="track"
                sortState={sortState}
                onSortChange={setSortState}
              />
            </TableHead>
            <TableHead>
              <SortableTableHead
                label="Track ID"
                sortKey="trackId"
                sortState={sortState}
                onSortChange={setSortState}
              />
            </TableHead>
            <TableHead>
              <SortableTableHead
                label="Interest"
                sortKey="interest"
                sortState={sortState}
                onSortChange={setSortState}
              />
            </TableHead>
            <TableHead>
              <SortableTableHead
                label="Year Level"
                sortKey="yearLevel"
                sortState={sortState}
                onSortChange={setSortState}
              />
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading ? (
            <StudentTableSkeleton />
          ) : students.length > 0 ? (
            sortedRows.map((student, index) => (
              <TableRow key={student.userId}>
                <TableCell>{index + 1}</TableCell>
                <TableCell className="font-medium">
                  {student.firstName} {student.lastName}
                </TableCell>
                <TableCell>
                  <Badge variant="outline">{student.trackCode}</Badge>
                </TableCell>
                <TableCell>{student.trackId}</TableCell>
                <TableCell>
                  {student.interests.length > 0 ? (
                    <div className="flex flex-wrap gap-1">
                      {student.interests.map((interest) => (
                        <Badge key={interest} variant="secondary">
                          {interest}
                        </Badge>
                      ))}
                    </div>
                  ) : (
                    <span className="text-muted-foreground">N/A</span>
                  )}
                </TableCell>
                <TableCell>{student.yearLevel ?? "N/A"}</TableCell>
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell colSpan={6} className="h-24 text-center">
                No individual students found.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}
