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

type IndividualStudentTableProps = {
  students: IndividualStudent[];
  isLoading?: boolean;
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
  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>#</TableHead>
            <TableHead>Name</TableHead>
            <TableHead>Track</TableHead>
            <TableHead>Track ID</TableHead>
            <TableHead>Year Level</TableHead>
            <TableHead>Country</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading ? (
            <StudentTableSkeleton />
          ) : students.length > 0 ? (
            students.map((student, index) => (
              <TableRow key={student.userId}>
                <TableCell>{index + 1}</TableCell>
                <TableCell className="font-medium">
                  {student.firstName} {student.lastName}
                </TableCell>
                <TableCell>
                  <Badge variant="outline">{student.trackCode}</Badge>
                </TableCell>
                <TableCell>{student.trackId}</TableCell>
                <TableCell>{student.yearLevel ?? "N/A"}</TableCell>
                <TableCell>{student.countryName}</TableCell>
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
