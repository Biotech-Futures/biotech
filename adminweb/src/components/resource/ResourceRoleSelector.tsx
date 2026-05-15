import { Badge } from "@/components/ui/badge";
import type { ResourceRole, VisibilityScope } from "@/type/resource";

interface ResourceRoleSelectorProps {
  mode: "view" | "edit";
  roles: ResourceRole[];
  selectedRoleIds?: number[];
  visibleRoleSlugs?: string[];
  visibilityScope?: VisibilityScope;
  onSelectedRoleIdsChange?: (roleIds: number[]) => void;
  helperText?: string;
}

export function ResourceRoleSelector({
  mode,
  roles,
  selectedRoleIds = [],
  visibleRoleSlugs = [],
  visibilityScope,
  onSelectedRoleIdsChange,
  helperText,
}: ResourceRoleSelectorProps) {
  const nonAdminRoles = roles.filter((role) => role.slug !== "admin");

  if (mode === "view") {
    if (visibilityScope === "global") {
      return (
        <span className="text-sm text-muted-foreground">Global visibility</span>
      );
    }

    if (!visibleRoleSlugs.length) {
      return (
        <span className="text-sm text-muted-foreground">
          Admin default visibility
        </span>
      );
    }

    return (
      <div className="flex flex-wrap items-center gap-2">
        {visibleRoleSlugs.map((slug) => (
          <Badge key={slug} variant="outline">
            {slug}
          </Badge>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        {nonAdminRoles.map((role) => {
          const checked = selectedRoleIds.includes(role.id);
          return (
            <label key={role.id} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={checked}
                onChange={(event) => {
                  const nextRoleIds = event.target.checked
                    ? [...selectedRoleIds, role.id]
                    : selectedRoleIds.filter((item) => item !== role.id);
                  onSelectedRoleIdsChange?.(nextRoleIds);
                }}
              />
              <span>{role.slug}</span>
            </label>
          );
        })}
      </div>
    </div>
  );
}
