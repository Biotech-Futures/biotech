import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { StudentStateOption } from "@/query/student";
import type { CountryOption } from "@/type/user";

interface StudentFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  country: string | undefined;
  onCountryChange: (value: string | undefined) => void;
  state: string | undefined;
  onStateChange: (value: string | undefined) => void;
  countries?: CountryOption[];
  states?: StudentStateOption[];
  isLoadingStates?: boolean;
  inGroup: "yes" | "no" | "all";
  onInGroupChange: (value: "yes" | "no" | "all") => void;
}

export function StudentFilters({
  search,
  onSearchChange,
  country,
  onCountryChange,
  state,
  onStateChange,
  countries = [],
  states = [],
  isLoadingStates = false,
  inGroup,
  onInGroupChange,
}: StudentFiltersProps) {
  // A state belongs to a country; once one is picked, only its states apply.
  const visibleStates = country
    ? states.filter((item) => item.countryName === country)
    : states;

  return (
    <div className="grid gap-4 md:grid-cols-4">
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
        <Label htmlFor="student-country">Country</Label>
        <Select
          value={country ?? "all"}
          onValueChange={(value) =>
            onCountryChange(value === "all" ? undefined : value)
          }
        >
          <SelectTrigger id="student-country">
            <SelectValue placeholder="All countries" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All countries</SelectItem>
            {countries.map((item) => (
              <SelectItem key={item.id} value={item.countryName}>
                {item.countryName}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-1">
        <Label htmlFor="student-state">State</Label>
        <Select
          value={state ?? "all"}
          onValueChange={(value) =>
            onStateChange(value === "all" ? undefined : value)
          }
        >
          <SelectTrigger id="student-state">
            <SelectValue placeholder="All states" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All states</SelectItem>
            {isLoadingStates && visibleStates.length === 0 && (
              <SelectItem value="loading" disabled>
                Loading states...
              </SelectItem>
            )}
            {visibleStates.map((item) => (
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
