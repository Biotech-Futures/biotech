import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { SearchIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export const Route = createFileRoute("/_auth/grading/by-group")({
  component: GradingByGroup,
});

function GradingByGroup() {
  const navigate = useNavigate();
  const [groupId, setGroupId] = useState("");

  return (
    <div className="space-y-3 max-w-xl">
      <p className="text-sm text-muted-foreground">
        Every component for a single group. Enter the group's ID.
      </p>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          const n = Number(groupId);
          if (!Number.isFinite(n) || n <= 0) return;
          void navigate({
            to: "/grading/groups/$groupId",
            params: { groupId: String(n) },
          });
        }}
      >
        <div className="relative flex-1">
          <SearchIcon className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-[calc(50%+2px)] size-4 text-muted-foreground" />
          <Input
            type="number"
            min={1}
            placeholder="Group ID"
            value={groupId}
            onChange={(e) => setGroupId(e.target.value)}
            className="pl-8 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
          />
        </div>
        <Button type="submit">Open</Button>
      </form>
    </div>
  );
}
