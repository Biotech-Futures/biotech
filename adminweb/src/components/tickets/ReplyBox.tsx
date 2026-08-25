import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

const MAX_BODY_LENGTH = 2000;

type Props = {
  isPending: boolean;
  onSend: (body: string, files: File[]) => void;
};

export function ReplyBox({ isPending, onSend }: Props) {
  const [body, setBody] = useState("");
  const [files, setFiles] = useState<File[]>([]);

  const send = () => {
    if (!body.trim()) return;
    onSend(body.trim(), files);
    setBody("");
    setFiles([]);
  };

  return (
    <div className="space-y-2 rounded-md border p-3">
      <p className="text-sm font-medium">Reply to the requester</p>
      <Textarea
        value={body}
        maxLength={MAX_BODY_LENGTH}
        onChange={(event) => setBody(event.target.value)}
        placeholder="This goes to the person who raised the ticket, and they are emailed about it."
        rows={4}
      />
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="file"
          multiple
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
    </div>
  );
}
