import { useId } from "react";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useMentorPrefs } from "@/store/mentorPrefs";
import { cn } from "@/lib/utils";

/** One shared, persisted setting — every mentor pick surface renders this. */
export function ShowFullMentorsToggle({ className }: { className?: string }) {
  const showFullMentors = useMentorPrefs((s) => s.showFullMentors);
  const setShowFullMentors = useMentorPrefs((s) => s.setShowFullMentors);
  // Two of these can be mounted at once (panel header + an open dialog), so the
  // id must be per-instance or the label targets the wrong switch.
  const id = useId();

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <Switch
        id={id}
        checked={showFullMentors}
        onCheckedChange={setShowFullMentors}
      />
      <Label
        htmlFor={id}
        className="text-xs font-normal text-muted-foreground"
      >
        Show mentors at capacity
      </Label>
    </div>
  );
}
