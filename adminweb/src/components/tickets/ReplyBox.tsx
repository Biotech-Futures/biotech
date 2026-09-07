import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ticketRefusalReason } from "@/lib/ticketError";

const MAX_BODY_LENGTH = 2000;

type Props = {
  isPending: boolean;
  /** Resolves when the message is stored. Rejects, so a failed send keeps
   *  what was typed instead of throwing it away. */
  onSend: (
    body: string,
    files: File[],
    moveToPending: boolean,
  ) => Promise<unknown>;
};

export function ReplyBox({ isPending, onSend }: Props) {
  const [body, setBody] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  // Off by default: most replies are an answer, not a question.
  const [moveToPending, setMoveToPending] = useState(false);

  const [error, setError] = useState("");

  // Cleared only once the server has it. Clearing on click threw away a long
  // reply the moment anything went wrong — a rejected attachment, an expired
  // session — and left no trace on screen that it had gone.
  const send = async () => {
    if (!body.trim()) return;
    setError("");
    try {
      await onSend(body.trim(), files, moveToPending);
      setBody("");
      setFiles([]);
      setMoveToPending(false);
    } catch (failure) {
      // Say what the server said. An 11 MB attachment is refused with
      // "Attachment exceeds the maximum allowed size of 10 MB.", and telling
      // the agent to try again instead is worse than saying nothing: the same
      // send fails the same way however many times they click.
      //
      // ticketRefusalReason answers with nothing for a dropped connection, and
      // also for the failures whose wording is DRF's rather than ours. The
      // sentence below covers all of those: it keeps the text and asks for
      // another go, which is right for a fault and no worse than a machine
      // message nobody can act on.
      const reason = ticketRefusalReason(failure);
      setError(
        reason
          ? `${reason} Your text is still here.`
          : "That did not send. Your text is still here — try again.",
      );
    }
  };

  return (
    <div className="space-y-2 rounded-md border p-3">
      <p className="text-sm font-medium">Reply to the requester</p>
      <Textarea
        // Same gap as the file input below: the heading above is visible but
        // not programmatically tied to this box.
        aria-label="Reply to the requester"
        value={body}
        maxLength={MAX_BODY_LENGTH}
        onChange={(event) => setBody(event.target.value)}
        placeholder="This goes to the person who raised the ticket, and they are emailed about it."
        rows={4}
      />
      <div className="flex items-center gap-2">
        <Checkbox
          id="move-to-pending"
          checked={moveToPending}
          onCheckedChange={(checked) => setMoveToPending(checked === true)}
        />
        <Label htmlFor="move-to-pending" className="text-xs font-normal">
          I have asked them for something — wait for their reply
        </Label>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="file"
          multiple
          // The two file pickers in this drawer had no accessible name at all.
          // A bare file input computes to the empty string — the "Choose File"
          // text belongs to a button inside the browser's own shadow DOM, so a
          // screen reader announces the same thing for both of them. One of
          // these attaches to a reply the student is emailed; the other
          // attaches to a note they must never see.
          aria-label="Attach files to this reply"
          accept=".pdf,.png,.jpg,.jpeg,.docx"
          className="text-muted-foreground max-w-[16rem] text-xs"
          onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
        />
        <span className="text-muted-foreground ml-auto text-xs">
          {body.length}/{MAX_BODY_LENGTH}
        </span>
        <Button size="sm" disabled={isPending || !body.trim()} onClick={send}>
          {isPending ? "Sending…" : "Send reply"}
        </Button>
      </div>
      {error && (
        <p className="text-destructive text-xs" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
