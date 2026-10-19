import { createFileRoute, Link } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/_auth/grading/by-component")({
  component: GradingByComponent,
});

// Component codes are hard-coded here to match the seed migration; a proper
// admin-editable list can replace this once the component-CRUD lands.
const COMPONENTS: { code: string; name: string }[] = [
  { code: "SAQ", name: "Short Answer Questions" },
  { code: "POSTER", name: "A2 Poster" },
  { code: "REPORT", name: "Scientific Report" },
  { code: "PROTOTYPE", name: "Prototype" },
];

function GradingByComponent() {
  return (
    <div className="space-y-3 max-w-xl">
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
    </div>
  );
}
