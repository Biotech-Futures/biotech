import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ClipboardListIcon, UsersIcon } from "lucide-react";

export const Route = createFileRoute("/_auth/grading/")({
  component: GradingIndex,
});

// Two entry points, matching the spec's two marking flows:
//   - By component ("sit down and mark all posters")
//   - By group   ("go into group 20, mark everything they submitted")
// Component codes are hard-coded here to match the seed migration; a proper
// admin-editable list can replace this once the component-CRUD lands.
const COMPONENTS: { code: string; name: string }[] = [
  { code: "SAQ", name: "Short Answer Questions" },
  { code: "POSTER", name: "A2 Poster" },
  { code: "REPORT", name: "Scientific Report" },
  { code: "PROTOTYPE", name: "Prototype" },
];

function GradingIndex() {
  const navigate = useNavigate();
  const [groupId, setGroupId] = useState("");

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <ClipboardListIcon className="size-5" />
          <h3 className="font-semibold">Mark by component</h3>
        </div>
        <p className="text-sm text-muted-foreground">
          One component at a time, across every group.
        </p>
        <ul className="space-y-1">
          {COMPONENTS.map((c) => (
            <li key={c.code}>
              <Button asChild variant="outline" className="w-full justify-start">
                <Link to="/grading/components/$code" params={{ code: c.code }}>
                  {c.name}
                </Link>
              </Button>
            </li>
          ))}
        </ul>
      </section>

      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <UsersIcon className="size-5" />
          <h3 className="font-semibold">Mark by group</h3>
        </div>
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
          <Input
            type="number"
            min={1}
            placeholder="Group ID"
            value={groupId}
            onChange={(e) => setGroupId(e.target.value)}
          />
          <Button type="submit">Open</Button>
        </form>
      </section>
    </div>
  );
}
