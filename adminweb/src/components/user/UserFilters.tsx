import { useMemo } from "react";
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
  labelizeUserRole,
  type CountryOption,
  type StateOption,
  type UserRole,
} from "@/type/user";

interface UserFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  role: UserRole | "all";
  onRoleChange: (value: UserRole | "all") => void;
  country: string | "all";
  onCountryChange: (value: string | "all") => void;
  state: string | "all";
  onStateChange: (value: string | "all") => void;
  countries?: CountryOption[];
  states?: StateOption[];
  status: "all" | "active" | "inactive";
  onStatusChange: (value: "all" | "active" | "inactive") => void;
}

export function UserFilters({
  search,
  onSearchChange,
  role,
  onRoleChange,
  country,
  onCountryChange,
  state,
  onStateChange,
  countries: countryOptions,
  states,
  status,
  onStatusChange,
}: UserFiltersProps) {
  const availableStates = useMemo(() => states ?? [], [states]);

  // From the countries lookup, not the states list: most users have no state, so
  // deriving this from states would hide their country from the filter entirely.
  const countries = useMemo(
    () =>
      (countryOptions ?? [])
        .map((item) => item.countryName)
        .sort((a, b) => a.localeCompare(b)),
    [countryOptions],
  );

  // Cascade: once a country is picked, only its states are selectable.
  const visibleStates = useMemo(
    () =>
      country === "all"
        ? availableStates
        : availableStates.filter((item) => item.countryName === country),
    [availableStates, country],
  );

  return (
    <div className="grid grid-cols-1 items-end gap-3 sm:grid-cols-2 xl:grid-cols-5">
      <div className="space-y-1.5">
        <Label htmlFor="user-search">Search</Label>
        <Input
          id="user-search"
          placeholder="Name or email"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="user-role">Role</Label>
        <Select
          value={role}
          onValueChange={(value) => onRoleChange(value as UserRole | "all")}
        >
          <SelectTrigger id="user-role" className="w-full">
            <SelectValue placeholder="All roles" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All roles</SelectItem>
            {USER_ROLES.map((item) => (
              <SelectItem key={item} value={item}>
                {labelizeUserRole(item)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="user-country">Country</Label>
        <Select value={country} onValueChange={onCountryChange}>
          <SelectTrigger id="user-country" className="w-full">
            <SelectValue placeholder="All countries" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All countries</SelectItem>
            {countries.map((item) => (
              <SelectItem key={item} value={item}>
                {item}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="user-state">State</Label>
        <Select value={state} onValueChange={onStateChange}>
          <SelectTrigger id="user-state" className="w-full">
            <SelectValue placeholder="All states" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All states</SelectItem>
            {visibleStates.map((item) => (
              <SelectItem key={item.id} value={item.stateName}>
                {/* State names repeat across countries, so qualify them until a country narrows the list. */}
                {country === "all" && item.countryName
                  ? `${item.stateName} · ${item.countryName}`
                  : item.stateName}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="user-status">Status</Label>
        <Select
          value={status}
          onValueChange={(value) =>
            onStatusChange(value as "all" | "active" | "inactive")
          }
        >
          <SelectTrigger id="user-status" className="w-full">
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
