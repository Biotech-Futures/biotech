import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { useGetAnnouncement } from "@/query/announcement";

type Props = {
  id: number | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

function scopeLabel(scope: string) {
  if (scope === "global") return "All users";
  if (scope === "track_based") return "By track";
  if (scope === "role_based") return "By role";
  if (scope === "track_role_based") return "By track & role";
  return scope;
}

export function AnnouncementDetailSheet({ id, open, onOpenChange }: Props) {
  const { data, isPending } = useGetAnnouncement(id);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-2xl overflow-y-auto">
        <SheetHeader>
          <SheetTitle>{data?.title ?? "Announcement"}</SheetTitle>
        </SheetHeader>

        {isPending ? (
          <div className="py-8 text-center text-sm text-muted-foreground">
            Loading...
          </div>
        ) : data ? (
          <div className="space-y-4 py-4">
            <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              <Badge variant="outline">{scopeLabel(data.visibilityScope)}</Badge>
              {data.trackName && <span>{data.trackName}</span>}
              <span>·</span>
              <span>{new Date(data.publishedAt).toLocaleString()}</span>
              {data.archivedAt && <Badge variant="secondary">Archived</Badge>}
            </div>

            <div
              className="prose prose-sm max-w-none rounded-md border p-4"
              dangerouslySetInnerHTML={{ __html: data.body }}
            />
          </div>
        ) : (
          <div className="py-8 text-center text-sm text-muted-foreground">
            Announcement not found.
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
