import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[95vw] sm:max-w-5xl max-h-[92vh] overflow-y-auto p-0">
        <DialogHeader className="px-8 pt-7 pb-4 border-b">
          <DialogTitle className="text-xl leading-snug pr-6">
            {data?.title ?? "Announcement"}
          </DialogTitle>
          {data && (
            <div className="flex flex-wrap items-center gap-2 pt-1 text-sm text-muted-foreground">
              <Badge variant="outline">{scopeLabel(data.visibilityScope)}</Badge>
              {data.trackName && <span>{data.trackName}</span>}
              <span>·</span>
              <span>{new Date(data.publishedAt).toLocaleString()}</span>
              {data.archivedAt && <Badge variant="secondary">Archived</Badge>}
            </div>
          )}
        </DialogHeader>

        {isPending ? (
          <div className="px-8 py-12 text-center text-sm text-muted-foreground">
            Loading…
          </div>
        ) : data ? (
          <div
            className={[
              "px-8 py-6",
              "prose prose-sm max-w-none",
              // links
              "[&_a]:text-primary [&_a]:underline",
              // images
              "[&_img]:max-w-full [&_img]:rounded-md",
              // tables
              "[&_table]:w-full [&_table]:border-collapse [&_table]:my-3",
              "[&_th]:border [&_th]:border-border [&_th]:px-3 [&_th]:py-2 [&_th]:bg-muted [&_th]:font-semibold [&_th]:text-left",
              "[&_td]:border [&_td]:border-border [&_td]:px-3 [&_td]:py-2",
            ].join(" ")}
            dangerouslySetInnerHTML={{ __html: data.body }}
          />
        ) : (
          <div className="px-8 py-12 text-center text-sm text-muted-foreground">
            Announcement not found.
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
