import { useState } from "react";
import { useQueryUnmatchedGroups } from "@/query/mentorMatch";
import { Badge } from "@/components/ui/badge";
import { ChevronDownIcon, ChevronRightIcon } from "lucide-react";

export function UnmatchedGroupsPanel() {
  const { data, isPending } = useQueryUnmatchedGroups();
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());

  const groups = data?.data ?? [];

  function toggleExpand(id: number) {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  if (isPending) {
    return <p className="text-sm text-muted-foreground">Loading unmatched groups...</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <h2 className="text-base font-semibold">Unmatched Groups</h2>
        <Badge variant="secondary">{groups.length}</Badge>
      </div>

      {groups.length === 0 ? (
        <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
          All groups have a mentor assigned.
        </div>
      ) : (
        <div className="rounded-xl border bg-card divide-y">
          {groups.map((g) => {
            const isExpanded = expandedIds.has(g.groupId);
            return (
              <div key={g.groupId}>
                <button
                  className="w-full flex items-center justify-between px-4 py-3 hover:bg-muted/40 transition-colors text-left"
                  onClick={() => toggleExpand(g.groupId)}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    {isExpanded ? (
                      <ChevronDownIcon className="size-4 text-muted-foreground flex-shrink-0" />
                    ) : (
                      <ChevronRightIcon className="size-4 text-muted-foreground flex-shrink-0" />
                    )}
                    <span className="font-medium truncate">{g.groupName}</span>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0 ml-2">
                    <Badge variant="outline" className="text-xs">{g.trackCode}</Badge>
                    <span className="text-xs text-muted-foreground">{g.studentCount} students</span>
                  </div>
                </button>

                {isExpanded && (
                  <div className="px-4 pb-4 pt-2 bg-muted/10 space-y-3">
                    {g.students && g.students.length > 0 ? (
                      <div className="space-y-2">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                          Students
                        </p>
                        <div className="space-y-1.5">
                          {g.students.map((s) => (
                            <div key={s.name} className="rounded border bg-background px-3 py-2">
                              <p className="text-sm font-medium">{s.name}</p>
                              {s.interests.length > 0 && (
                                <div className="mt-1 flex flex-wrap gap-1">
                                  {s.interests.map((i) => (
                                    <Badge key={i} variant="outline" className="text-[10px] px-1.5 py-0">
                                      {i}
                                    </Badge>
                                  ))}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-1">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                          Student Interests
                        </p>
                        <div className="flex flex-wrap gap-1">
                          {[...new Set(g.studentInterests)].map((i) => (
                            <Badge key={i} variant="outline" className="text-xs">
                              {i}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
