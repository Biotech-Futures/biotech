import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import {
  TICKET_CATEGORY_OPTIONS,
  TICKET_PRIORITY_LABELS,
  TICKET_STATUS_LABELS,
  type AssigneeOption,
  type RegionOption,
  type TicketFilters,
} from "@/schema/ticket";

// The Select component cannot carry an empty value, so "no filter" travels as
// this sentinel and is stripped before the request is built.
export const ANY = "__any__";

type Props = {
  filters: TicketFilters;
  onChange: (next: TicketFilters) => void;
  regions: RegionOption[];
  assignees: AssigneeOption[];
};

export function FilterBar({ filters, onChange, regions, assignees }: Props) {
  const set = (key: keyof TicketFilters, value: string) =>
    onChange({ ...filters, [key]: value === ANY ? "" : value });

  const hasAny = Object.values(filters).some(Boolean);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Input
        value={filters.search ?? ""}
        onChange={(event) => onChange({ ...filters, search: event.target.value })}
        placeholder="Search number, subject, or requester"
        className="w-full sm:w-72"
        aria-label="Search tickets"
      />

      <Select value={filters.status || ANY} onValueChange={(v) => set("status", v)}>
        <SelectTrigger className="w-[150px]" aria-label="Filter by status">
          <SelectValue placeholder="Status" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ANY}>Any status</SelectItem>
          {Object.entries(TICKET_STATUS_LABELS).map(([value, label]) => (
            <SelectItem key={value} value={value}>
              {label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select value={filters.priority || ANY} onValueChange={(v) => set("priority", v)}>
        <SelectTrigger className="w-[140px]" aria-label="Filter by priority">
          <SelectValue placeholder="Priority" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ANY}>Any priority</SelectItem>
          {Object.entries(TICKET_PRIORITY_LABELS).map(([value, label]) => (
            <SelectItem key={value} value={value}>
              {label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select value={filters.category || ANY} onValueChange={(v) => set("category", v)}>
        <SelectTrigger className="w-[190px]" aria-label="Filter by category">
          <SelectValue placeholder="Category" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ANY}>Any category</SelectItem>
          {TICKET_CATEGORY_OPTIONS.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select value={filters.region || ANY} onValueChange={(v) => set("region", v)}>
        <SelectTrigger className="w-[160px]" aria-label="Filter by region">
          <SelectValue placeholder="Region" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ANY}>Any region</SelectItem>
          {regions.map((region) => (
            <SelectItem key={region.value} value={region.value}>
              {region.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select value={filters.assignee || ANY} onValueChange={(v) => set("assignee", v)}>
        <SelectTrigger className="w-[170px]" aria-label="Filter by assignee">
          <SelectValue placeholder="Assignee" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ANY}>Any assignee</SelectItem>
          {assignees.map((person) => (
            <SelectItem key={person.id} value={String(person.id)}>
              {person.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {hasAny && (
        <Button variant="ghost" size="sm" onClick={() => onChange({})}>
          Clear filters
        </Button>
      )}
    </div>
  );
}
