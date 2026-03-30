// Group filters component - separate search for name and group

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import type { Track } from "@/type/group";
import { TRACKS } from "@/type/group";
import { SearchIcon, UserIcon } from "lucide-react";
import { useState, useEffect, useRef, useCallback } from "react";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from "../ui/input-group";

interface GroupFiltersProps {
  searchName: string;
  onSearchNameChange: (value: string) => void;
  searchGroup: string;
  onSearchGroupChange: (value: string) => void;
  track: Track | undefined;
  onTrackChange: (value: Track | undefined) => void;
}

export function GroupFilters({
  searchName,
  onSearchNameChange,
  searchGroup,
  onSearchGroupChange,
  track,
  onTrackChange,
}: GroupFiltersProps) {
  const [localSearchName, setLocalSearchName] = useState(searchName);
  const [localSearchGroup, setLocalSearchGroup] = useState(searchGroup);
  const timeoutNameRef = useRef<NodeJS.Timeout | null>(null);
  const timeoutGroupRef = useRef<NodeJS.Timeout | null>(null);

  const debouncedSearchName = useCallback(
    (value: string) => {
      if (timeoutNameRef.current) {
        clearTimeout(timeoutNameRef.current);
      }
      timeoutNameRef.current = setTimeout(() => {
        onSearchNameChange(value);
      }, 300);
    },
    [onSearchNameChange],
  );

  const debouncedSearchGroup = useCallback(
    (value: string) => {
      if (timeoutGroupRef.current) {
        clearTimeout(timeoutGroupRef.current);
      }
      timeoutGroupRef.current = setTimeout(() => {
        onSearchGroupChange(value);
      }, 300);
    },
    [onSearchGroupChange],
  );

  useEffect(() => {
    setLocalSearchName(searchName);
    setLocalSearchGroup(searchGroup);
  }, [searchName, searchGroup]);

  useEffect(() => {
    return () => {
      if (timeoutNameRef.current) clearTimeout(timeoutNameRef.current);
      if (timeoutGroupRef.current) clearTimeout(timeoutGroupRef.current);
    };
  }, []);

  return (
    <div className="flex flex-col lg:flex-row gap-4 py-4">
      {/* Search by Group Name */}
      <div className="flex-1">
        <Label
          htmlFor="search-group"
          className="text-sm text-muted-foreground mb-1.5 block"
        >
          Search by Group
        </Label>
        <div className="relative">
          <InputGroup>
            <InputGroupAddon>
              <SearchIcon />
            </InputGroupAddon>
            <InputGroupInput
              id="search-group"
              placeholder="Group name..."
              value={localSearchGroup}
              onChange={(e) => {
                setLocalSearchGroup(e.target.value);
                debouncedSearchGroup(e.target.value);
              }}
              className="pl-9"
            />
          </InputGroup>
        </div>
      </div>

      {/* Search by Member Name */}
      <div className="flex-1">
        <Label
          htmlFor="search-name"
          className="text-sm text-muted-foreground mb-1.5 block"
        >
          Search by Member
        </Label>
        <div className="relative">
          <InputGroup>
            <InputGroupAddon>
              <UserIcon />
            </InputGroupAddon>
            <InputGroupInput
              id="search-name"
              placeholder="Member name..."
              value={localSearchName}
              onChange={(e) => {
                setLocalSearchName(e.target.value);
                debouncedSearchName(e.target.value);
              }}
              className="pl-9"
            />
          </InputGroup>
        </div>
      </div>

      {/* Track Filter */}
      <div className="w-full lg:w-45">
        <Label
          htmlFor="track-filter"
          className="text-sm text-muted-foreground mb-1.5 block"
        >
          Filter by Track
        </Label>
        <Select
          value={track ?? "all"}
          onValueChange={(value) => {
            onTrackChange(value === "all" ? undefined : (value as Track));
          }}
        >
          <SelectTrigger id="track-filter" className="min-w-32">
            <SelectValue placeholder="All Tracks" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Tracks</SelectItem>
            {TRACKS.map((t) => (
              <SelectItem key={t} value={t}>
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
