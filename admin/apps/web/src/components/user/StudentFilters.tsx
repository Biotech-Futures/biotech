import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { StudentTrack, TrackOption } from "@/type/user";
import { STUDENT_TRACKS } from "@/type/user";

interface StudentFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  yearLevel: string;
  onYearLevelChange: (value: string) => void;
  track: StudentTrack | undefined;
  onTrackChange: (value: StudentTrack | undefined) => void;
  tracks?: TrackOption[];
  isLoadingTracks?: boolean;
  interest: string;
  onInterestChange: (value: string) => void;
  inGroup: "yes" | "no" | "all";
  onInGroupChange: (value: "yes" | "no" | "all") => void;
}

export function StudentFilters({
  search,
  onSearchChange,
  yearLevel,
  onYearLevelChange,
  track,
  onTrackChange,
  tracks = [],
  isLoadingTracks = false,
  interest,
  onInterestChange,
  inGroup,
  onInGroupChange,
}: StudentFiltersProps) {
  const trackOptions =
    tracks.length > 0
      ? tracks.map((item) => item.trackCode)
      : STUDENT_TRACKS;

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
      <div className="space-y-1">
        <Label htmlFor="student-search">Search</Label>
        <Input
          id="student-search"
          placeholder="Name or email"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
        />
      </div>

      <div className="space-y-1">
        <Label htmlFor="student-year-level">Year</Label>
        <Select
          value={yearLevel || "all"}
          onValueChange={(value) =>
            onYearLevelChange(value === "all" ? "" : value)
          }
        >
          <SelectTrigger id="student-year-level">
            <SelectValue placeholder="All years" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All years</SelectItem>
            {[7, 8, 9, 10, 11, 12].map((n) => (
              <SelectItem key={n} value={String(n)}>
                Year {n}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-1">
        <Label htmlFor="student-track">Track</Label>
        <Select
          value={track ?? "all"}
          onValueChange={(value) =>
            onTrackChange(value === "all" ? undefined : (value as StudentTrack))
          }
        >
          <SelectTrigger id="student-track">
            <SelectValue placeholder="All tracks" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All tracks</SelectItem>
            {isLoadingTracks && tracks.length === 0 && (
              <SelectItem value="loading" disabled>
                Loading tracks...
              </SelectItem>
            )}
            {trackOptions.map((item) => (
              <SelectItem key={item} value={item}>
                {item}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-1">
        <Label htmlFor="student-interest">Interest</Label>
        <Input
          id="student-interest"
          placeholder="Interest keyword"
          value={interest}
          onChange={(e) => onInterestChange(e.target.value)}
        />
      </div>

      <div className="space-y-1">
        <Label htmlFor="student-group">In Group</Label>
        <Select
          value={inGroup}
          onValueChange={(value) =>
            onInGroupChange(value as "yes" | "no" | "all")
          }
        >
          <SelectTrigger id="student-group">
            <SelectValue placeholder="All" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            <SelectItem value="yes">Yes</SelectItem>
            <SelectItem value="no">No</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
