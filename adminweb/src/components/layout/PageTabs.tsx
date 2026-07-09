import { Link } from "@tanstack/react-router";
import { cn } from "@/lib/utils";

export type PageTab = {
  label: string;
  /** Route to navigate to. Kept as a plain string like the sidebar nav. */
  to: string;
  /** Match the current route exactly — use for a hub's index/default tab. */
  exact?: boolean;
};

/**
 * Route-backed tab strip: each tab is a real navigation link (URL changes,
 * only the outlet swaps). Uses aria-current + TanStack's data-status for the
 * active underline, so it stays honest for assistive tech and avoids Tailwind
 * class-order conflicts with activeProps.
 */
export function PageTabs({ tabs }: { tabs: PageTab[] }) {
  return (
    <nav aria-label="Section" className="flex items-center gap-1 border-b">
      {tabs.map((tab) => (
        <Link
          key={tab.to}
          to={tab.to}
          activeOptions={{ exact: tab.exact ?? false }}
          activeProps={{ "aria-current": "page" }}
          className={cn(
            "relative -mb-px inline-flex h-11 items-center rounded-t-md border-b-2 border-transparent px-3 text-sm font-medium text-muted-foreground transition-colors",
            "hover:text-foreground",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            "data-[status=active]:border-primary data-[status=active]:text-primary",
          )}
        >
          {tab.label}
        </Link>
      ))}
    </nav>
  );
}
