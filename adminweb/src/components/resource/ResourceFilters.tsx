import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { ArrowUpDown, SearchIcon } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { InputGroup, InputGroupAddon, InputGroupInput } from "../ui/input-group";
import type {
  ResourceOrder,
  ResourceTrackOption,
  ResourceTypeName,
  ResourceTypeOption,
} from "@/type/resource";

interface ResourceFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  uploader: string;
  onUploaderChange: (value: string) => void;
  trackId: number | undefined;
  onTrackIdChange: (value: number | undefined) => void;
  order: ResourceOrder;
  onOrderChange: (value: ResourceOrder) => void;
  type: ResourceTypeName | undefined;
  onTypeChange: (value: ResourceTypeName | undefined) => void;
  trackOptions: ResourceTrackOption[];
  typeOptions?: ResourceTypeOption[];
  actionSlot?: ReactNode;
}

export function ResourceFilters({
  search,
  onSearchChange,
  uploader,
  onUploaderChange,
  trackId,
  onTrackIdChange,
  order,
  onOrderChange,
  type,
  onTypeChange,
  trackOptions,
  typeOptions,
  actionSlot,
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

  const availableTypeOptions = typeOptions ?? [];

  return (
    <div className="p-4 space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-12 gap-4">
        <div className="md:col-span-1 xl:col-span-4">
            <Label htmlFor="resource-track" className="text-sm text-muted-foreground mb-1.5 block">
              Track
            </Label>
            <Select
              value={trackId === undefined ? "all" : String(trackId)}
              onValueChange={(value) =>
                onTrackIdChange(value === "all" ? undefined : Number(value))
              }
            >
              <SelectTrigger id="resource-track" className="w-full">
                <SelectValue placeholder="All Tracks" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Tracks</SelectItem>
                {trackOptions.map((track) => (
                  <SelectItem key={track.id} value={String(track.id)}>
                    {track.code}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="md:col-span-1 xl:col-span-4">
            <Label htmlFor="resource-type" className="text-sm text-muted-foreground mb-1.5 block">
              Type
            </Label>
            <Select
              value={type ?? "all"}
              onValueChange={(value) =>
                onTypeChange(value === "all" ? undefined : (value as ResourceTypeName))
              }
            >
              <SelectTrigger id="resource-type" className="w-full">
                <SelectValue placeholder="All Types" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                {availableTypeOptions.map((resourceType) => (
                  <SelectItem key={resourceType.value} value={resourceType.value}>
                    {resourceType.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

        <div className="md:col-span-2 xl:col-span-4">
          <Label htmlFor="resource-order" className="text-sm text-muted-foreground mb-1.5 block">
            Sort by Date
          </Label>
            <Select value={order} onValueChange={(value) => onOrderChange(value as ResourceOrder)}>
              <SelectTrigger id="resource-order" className="w-full">
                <ArrowUpDown className="size-4" />
                <SelectValue placeholder="Newest first" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="newest">Newest First</SelectItem>
                <SelectItem value="oldest">Oldest First</SelectItem>
              </SelectContent>
            </Select>
          </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="md:col-span-1">
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

        <div className="md:col-span-1">
          <Label
            htmlFor="resource-uploader"
            className="text-sm text-muted-foreground mb-1.5 block"
          >
            Search Uploader
          </Label>
          <InputGroup>
            <InputGroupAddon>
              <SearchIcon />
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

      </div>

      <div className="flex flex-wrap items-center justify-start gap-2 xl:justify-end">
        {actionSlot}
      </div>
    </div>
  );
}
