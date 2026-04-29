import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useQueryGroupMessages, useRemoveGroupMessage } from "@/query/group";
import type { Group } from "@/type/group";
import { AxiosError } from "axios";
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  MessageSquareIcon,
  Trash2Icon,
} from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

function formatMessageTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

interface GroupMessagesDialogProps {
  group: Group | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function GroupMessagesDialog({
  group,
  open,
  onOpenChange,
}: GroupMessagesDialogProps) {
  const [messagePage, setMessagePage] = useState(1);
  const groupId = group?.id ?? "";
  const { data, isPending, isError } = useQueryGroupMessages(groupId, {
    page: messagePage,
    limit: 50,
    enabled: open && Boolean(groupId),
  });
  const removeGroupMessage = useRemoveGroupMessage();

  useEffect(() => {
    setMessagePage(1);
  }, [groupId, open]);

  const messages = data?.data.items ?? [];
  const meta = data?.data;
  const hasLoadedMessages = Boolean(meta);
  const showBlockingError = isError && !hasLoadedMessages;

  async function handleRemoveMessage(messageId: string) {
    if (!group) return;

    const confirmed = window.confirm(
      "Remove this message from the group? This will hide it from the message history.",
    );
    if (!confirmed) return;

    try {
      await removeGroupMessage.mutateAsync({ groupId: group.id, messageId });
      toast.success("Message removed from group.");
    } catch (error) {
      const msg =
        error instanceof AxiosError
          ? ((error.response?.data as { msg?: string } | undefined)?.msg ??
            error.message)
          : "Could not remove message. Please try again.";
      toast.error(msg);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[85vh] max-w-[calc(100%-2rem)] grid-rows-none flex-col overflow-hidden sm:max-w-2xl">
        <DialogHeader className="shrink-0 pr-8">
          <DialogTitle className="flex items-center gap-2">
            <MessageSquareIcon className="size-5" />
            {group ? `${group.name} Messages` : "Group Messages"}
          </DialogTitle>
          <DialogDescription>
            View the message history for this group.
          </DialogDescription>
        </DialogHeader>

        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
          {meta && (
            <div className="text-xs text-muted-foreground">
              {meta.total} total messages
            </div>
          )}

          {isPending && (
            <div className="rounded-md bg-muted/50 p-3 text-sm text-muted-foreground">
              Loading messages...
            </div>
          )}

          {!isPending && !showBlockingError && messages.length === 0 && (
            <div className="rounded-md bg-muted/50 p-3 text-sm text-muted-foreground">
              No messages in this group yet.
            </div>
          )}

          {messages.map((message) => (
            <div key={message.id} className="rounded-md bg-muted/50 p-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate font-medium">
                    {message.sender.name || message.sender.email}
                  </p>
                  <p className="truncate text-xs text-muted-foreground">
                    {message.sender.email}
                  </p>
                </div>
                <div className="flex shrink-0 items-start gap-2">
                  <div className="text-right">
                    {message.sender.role && (
                      <Badge variant="outline" className="mb-1">
                        {message.sender.role}
                      </Badge>
                    )}
                    <p className="text-xs text-muted-foreground">
                      {formatMessageTime(message.sentAt)}
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="size-8 text-muted-foreground hover:text-destructive"
                    disabled={removeGroupMessage.isPending}
                    aria-label="Remove message from group"
                    title="Remove message from group"
                    onClick={() => void handleRemoveMessage(message.id)}
                  >
                    <Trash2Icon className="size-4" />
                  </Button>
                </div>
              </div>
              <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-relaxed">
                {message.text}
              </p>
              {message.editedAt && (
                <p className="mt-2 text-xs text-muted-foreground">
                  Edited {formatMessageTime(message.editedAt)}
                </p>
              )}
            </div>
          ))}
        </div>

        {meta && meta.total > meta.limit && (
          <div className="flex shrink-0 items-center justify-between gap-2 border-t pt-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setMessagePage((page) => Math.max(1, page - 1))}
              disabled={meta.page <= 1 || isPending}
            >
              <ChevronLeftIcon className="mr-1 size-4" />
              Previous
            </Button>
            <span className="text-xs text-muted-foreground">
              Page {meta.page} of {Math.ceil(meta.total / meta.limit)}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setMessagePage((page) => page + 1)}
              disabled={!meta.hasMore || isPending}
            >
              Next
              <ChevronRightIcon className="ml-1 size-4" />
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
