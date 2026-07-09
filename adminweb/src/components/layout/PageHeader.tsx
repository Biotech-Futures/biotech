import type { ReactNode } from "react";
import { PageTabs, type PageTab } from "./PageTabs";

/**
 * Shared page header: optional title/description, an optional right-aligned
 * actions slot, and an optional route-backed tab strip. Used by the People and
 * Groups hub layout routes to give the portal one consistent header treatment.
 */
export function PageHeader({
  title,
  description,
  tabs,
  actions,
}: {
  title?: string;
  description?: string;
  tabs?: PageTab[];
  actions?: ReactNode;
}) {
  return (
    <div className="space-y-3">
      {(title || actions) && (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            {title && (
              <h1 className="text-lg font-semibold tracking-tight">{title}</h1>
            )}
            {description && (
              <p className="text-sm text-muted-foreground">{description}</p>
            )}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
      )}
      {tabs && <PageTabs tabs={tabs} />}
    </div>
  );
}
