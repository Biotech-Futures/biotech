import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

const MAX_BODY_LENGTH = 2000;

type Props = {
  isPending: boolean;
  onSend: (body: string, files: File[]) => void;
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

  const send = () => {
    if (!body.trim()) return;
    onSend(body.trim(), files);
    setBody("");
    setFiles([]);
  };

  return (
    <div className="space-y-2 rounded-md border-2 border-dashed border-amber-400 bg-amber-50 p-3">
      <p className="flex items-center gap-1.5 text-sm font-semibold text-amber-900">
        <span aria-hidden="true">🔒</span>
        Internal note — the requester never sees this
      </p>
      <Textarea
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
    </div>
  );
}
