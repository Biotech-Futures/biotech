import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { SearchIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { InputGroup, InputGroupAddon, InputGroupInput } from "../ui/input-group";
import type { ResourceTypeName } from "@/type/resource";
import { RESOURCE_TYPES } from "@/type/resource";

interface ResourceFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  type: ResourceTypeName | undefined;
  onTypeChange: (value: ResourceTypeName | undefined) => void;
}

export function ResourceFilters({
  search,
  onSearchChange,
  type,
  onTypeChange,
}: ResourceFiltersProps) {
  const [localSearch, setLocalSearch] = useState(search);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    setLocalSearch(search);
  }, [search]);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  return (
    <div className="flex flex-col lg:flex-row gap-4 py-4">
      <div className="flex-1">
        <Label htmlFor="resource-search" className="text-sm text-muted-foreground mb-1.5 block">
          Search Resource
        </Label>
        <InputGroup>
          <InputGroupAddon>
            <SearchIcon />
          </InputGroupAddon>
          <InputGroupInput
            id="resource-search"
            placeholder="Resource name or description..."
            value={localSearch}
            onChange={(event) => {
              const value = event.target.value;
              setLocalSearch(value);
              if (timeoutRef.current) clearTimeout(timeoutRef.current);
              timeoutRef.current = setTimeout(() => {
                onSearchChange(value);
              }, 300);
            }}
            className="pl-9"
          />
        </InputGroup>
      </div>

      <div className="w-full lg:w-45">
        <Label htmlFor="resource-type" className="text-sm text-muted-foreground mb-1.5 block">
          Filter by Type
        </Label>
        <Select
          value={type ?? "all"}
          onValueChange={(value) =>
            onTypeChange(value === "all" ? undefined : (value as ResourceTypeName))
          }
        >
          <SelectTrigger id="resource-type" className="min-w-32">
            <SelectValue placeholder="All Types" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            {RESOURCE_TYPES.map((resourceType) => (
              <SelectItem key={resourceType} value={resourceType}>
                {resourceType.charAt(0).toUpperCase() + resourceType.slice(1)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
