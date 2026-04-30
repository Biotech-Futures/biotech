import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  USER_ROLES,
  type TrackOption,
  type UserRole,
  type UserTrack,
} from "@/type/user";

interface UserFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  role: UserRole | "all";
  onRoleChange: (value: UserRole | "all") => void;
  track: UserTrack | "all";
  onTrackChange: (value: UserTrack | "all") => void;
  tracks?: TrackOption[];
  status: "all" | "active" | "inactive";
  onStatusChange: (value: "all" | "active" | "inactive") => void;
}

export function UserFilters({
  search,
  onSearchChange,
  role,
  onRoleChange,
  track,
  onTrackChange,
  tracks,
  status,
  onStatusChange,
}: UserFiltersProps) {
  const availableTracks = (tracks ?? []).map((item) => item.trackName);

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <div className="space-y-1">
        <Label htmlFor="user-search">Search</Label>
        <Input
          id="user-search"
          placeholder="Name or email"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
        />
      </div>

      <div className="space-y-1">
        <Label htmlFor="user-role">Role</Label>
        <Select value={role} onValueChange={(value) => onRoleChange(value as UserRole | "all")}>
          <SelectTrigger id="user-role">
            <SelectValue placeholder="All roles" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All roles</SelectItem>
            {USER_ROLES.map((item) => (
              <SelectItem key={item} value={item}>
                {item}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-1">
        <Label htmlFor="user-track">Track</Label>
        <Select value={track} onValueChange={(value) => onTrackChange(value as UserTrack | "all")}>
          <SelectTrigger id="user-track">
            <SelectValue placeholder="All tracks" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All tracks</SelectItem>
            {availableTracks.map((item) => (
              <SelectItem key={item} value={item}>
                {item}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-1">
        <Label htmlFor="user-status">Status</Label>
        <Select value={status} onValueChange={(value) => onStatusChange(value as "all" | "active" | "inactive")}>
          <SelectTrigger id="user-status">
            <SelectValue placeholder="All statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="inactive">Inactive</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
