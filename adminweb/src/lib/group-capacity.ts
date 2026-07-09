import type { Group } from "@/type/group";

/** Max students per group (until the backend exposes a per-group cap). */
export const DEFAULT_GROUP_MAX_SIZE = 5;

export type GroupWithCapacity = {
  id: Group["id"];
  name: string;
  studentCount: number;
  /** Free student seats remaining (>= 0). */
  remaining: number;
};

/** How many students currently belong to a group. */
export function studentCount(group: Group): number {
  return group.members.filter((member) => member.role === "student").length;
}

/**
 * Groups that still have a free student seat, richest-first then A→Z. Shared by
 * every "assign student to group" surface so the capacity rule lives in one
 * place instead of being copy-pasted per dialog.
 */
export function groupsWithFreeSeats(
  groups: Group[],
  maxSize: number = DEFAULT_GROUP_MAX_SIZE,
): GroupWithCapacity[] {
  return groups
    .map((group) => {
      const count = studentCount(group);
      return {
        id: group.id,
        name: group.name,
        studentCount: count,
        remaining: Math.max(0, maxSize - count),
      };
    })
    .filter((group) => group.remaining > 0)
    .sort((a, b) => {
      if (a.remaining !== b.remaining) return b.remaining - a.remaining;
      return a.name.localeCompare(b.name);
    });
}
