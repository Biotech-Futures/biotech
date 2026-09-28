import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ticketRefusalReason } from "@/lib/ticketError";

const MAX_BODY_LENGTH = 2000;

type Props = {
  isPending: boolean;
  /** Resolves when the message is stored. Rejects, so a failed send keeps
   *  what was typed instead of throwing it away. */
  onSend: (body: string, files: File[]) => Promise<unknown>;
};

/**
 * Deliberately does not look like the reply box.
 *
 * These two controls sit next to each other and do opposite things: one is
 * read by a student, the other must never be. The amber frame, the lock and
 * the wording are all there so that telling them apart does not depend on
 * reading a label carefully at the end of a long shift.
 */
export function InternalNoteBox({ isPending, onSend }: Props) {
  const [body, setBody] = useState("");
  const [files, setFiles] = useState<File[]>([]);

  const [error, setError] = useState("");

  // Cleared only once the server has it. Clearing on click threw away a long
  // reply the moment anything went wrong — a rejected attachment, an expired
  // session — and left no trace on screen that it had gone.
  const send = async () => {
    if (!body.trim()) return;
    setError("");
    try {
      await onSend(body.trim(), files);
      setBody("");
      setFiles([]);
    } catch (failure) {
      // Same reasoning as the reply box: the refusals an agent meets here are
      // ones they can act on, and a hidden reason turns one rejected file into
      // a loop of identical failures. Anything ticketRefusalReason declines to
      // read, a dropped connection or a machine message, falls to the standing
      // sentence below.
      const reason = ticketRefusalReason(failure);
      setError(
        reason
          ? `${reason} Your text is still here.`
          : "That did not send. Your text is still here — try again.",
      );
    }
  };

  return (
    <div className="space-y-2 rounded-md border-2 border-dashed border-amber-400 bg-amber-50 p-3">
      <p className="flex items-center gap-1.5 text-sm font-semibold text-amber-900">
        <span aria-hidden="true">🔒</span>
        Internal note — the requester never sees this
      </p>
      <Textarea
        aria-label="Internal note, not visible to the requester"
        value={body}
        maxLength={MAX_BODY_LENGTH}
        onChange={(event) => setBody(event.target.value)}
        placeholder="Visible to support only. No email is sent and the requester's ticket shows no change."
        rows={4}
        className="border-amber-300 bg-white"
      />
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="file"
          multiple
          // The visible frame, the lock and the wording all say which of the
          // two boxes this is; none of that reaches a screen reader through
          // the file input, which had no accessible name of its own. See the
          // matching note in ReplyBox.
          aria-label="Attach files to this internal note"
          accept=".pdf,.png,.jpg,.jpeg,.docx"
          className="max-w-[16rem] text-xs text-amber-900"
          onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
        />
        <span className="ml-auto text-xs text-amber-900">
          {body.length}/{MAX_BODY_LENGTH}
        </span>
        <Button
          size="sm"
          variant="secondary"
          disabled={isPending || !body.trim()}
          onClick={send}
        >
          {isPending ? "Saving…" : "Add internal note"}
        </Button>
      </div>
      {error && (
        <p className="text-xs font-medium text-amber-900" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
