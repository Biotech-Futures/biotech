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
  type StateOption,
  type UserRole,
} from "@/type/user";

interface UserFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  role: UserRole | "all";
  onRoleChange: (value: UserRole | "all") => void;
  state: string | "all";
  onStateChange: (value: string | "all") => void;
  states?: StateOption[];
  status: "all" | "active" | "inactive";
  onStatusChange: (value: "all" | "active" | "inactive") => void;
}

export function UserFilters({
  search,
  onSearchChange,
  role,
  onRoleChange,
  state,
  onStateChange,
  states,
  status,
  onStatusChange,
}: UserFiltersProps) {
  const availableStates = states ?? [];

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
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
        <Select
          value={role}
          onValueChange={(value) => onRoleChange(value as UserRole | "all")}
        >
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
        <Label htmlFor="user-state">State</Label>
        <Select
          value={state}
          onValueChange={(value) => onStateChange(value)}
        >
          <SelectTrigger id="user-state">
            <SelectValue placeholder="All states" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All states</SelectItem>
            {availableStates.map((item) => (
              <SelectItem key={item.id} value={item.stateName}>
                {item.countryName
                  ? `${item.stateName} · ${item.countryName}`
                  : item.stateName}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-1">
        <Label htmlFor="user-status">Status</Label>
        <Select
          value={status}
          onValueChange={(value) =>
            onStatusChange(value as "all" | "active" | "inactive")
          }
        >
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
