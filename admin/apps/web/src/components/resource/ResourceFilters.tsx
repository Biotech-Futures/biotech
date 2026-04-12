import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { ArrowUpDown, SearchIcon, UserIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { InputGroup, InputGroupAddon, InputGroupInput } from "../ui/input-group";
import type { ResourceOrder, ResourceTypeName } from "@/type/resource";
import { RESOURCE_TYPES } from "@/type/resource";

interface ResourceFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  uploader: string;
  onUploaderChange: (value: string) => void;
  order: ResourceOrder;
  onOrderChange: (value: ResourceOrder) => void;
  type: ResourceTypeName | undefined;
  onTypeChange: (value: ResourceTypeName | undefined) => void;
}

export function ResourceFilters({
  search,
  onSearchChange,
  uploader,
  onUploaderChange,
  order,
  onOrderChange,
  type,
  onTypeChange,
}: ResourceFiltersProps) {
  const [localSearch, setLocalSearch] = useState(search);
  const [localUploader, setLocalUploader] = useState(uploader);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const timeoutUploaderRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    setLocalSearch(search);
    setLocalUploader(uploader);
  }, [search, uploader]);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      if (timeoutUploaderRef.current) clearTimeout(timeoutUploaderRef.current);
    };
  }, []);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 py-4">
      <div className="lg:col-span-3">
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

      <div className="lg:col-span-3">
        <Label
          htmlFor="resource-uploader"
          className="text-sm text-muted-foreground mb-1.5 block"
        >
          Search Uploader
        </Label>
        <InputGroup>
          <InputGroupAddon>
            <UserIcon />
          </InputGroupAddon>
          <InputGroupInput
            id="resource-uploader"
            placeholder="Uploader name or email..."
            value={localUploader}
            onChange={(event) => {
              const value = event.target.value;
              setLocalUploader(value);
              if (timeoutUploaderRef.current) clearTimeout(timeoutUploaderRef.current);
              timeoutUploaderRef.current = setTimeout(() => {
                onUploaderChange(value);
              }, 300);
            }}
            className="pl-9"
          />
        </InputGroup>
      </div>

      <div className="w-full lg:col-span-2">
        <Label htmlFor="resource-order" className="text-sm text-muted-foreground mb-1.5 block">
          Sort by Date
        </Label>
        <Select value={order} onValueChange={(value) => onOrderChange(value as ResourceOrder)}>
          <SelectTrigger id="resource-order" className="min-w-32">
            <ArrowUpDown className="size-4" />
            <SelectValue placeholder="Newest first" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="newest">Newest First</SelectItem>
            <SelectItem value="oldest">Oldest First</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="w-full lg:col-span-2">
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
