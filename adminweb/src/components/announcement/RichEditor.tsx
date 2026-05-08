import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

type Props = {
  value: string;
  onChange: (html: string) => void;
  placeholder?: string;
};

export function RichEditor({ value, onChange, placeholder }: Props) {
  const [rawMode, setRawMode] = useState(false);

  const editor = useEditor({
    extensions: [
      StarterKit,
      Placeholder.configure({ placeholder: placeholder ?? "Write your announcement..." }),
    ],
    content: value,
    onUpdate: ({ editor }) => {
      onChange(editor.getHTML());
    },
  });

  function toggleMode() {
    if (!editor) return;
    if (rawMode) {
      editor.commands.setContent(value);
    }
    setRawMode((prev) => !prev);
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">Content</span>
        <Button type="button" variant="outline" size="sm" onClick={toggleMode}>
          {rawMode ? "WYSIWYG" : "Raw HTML"}
        </Button>
      </div>

      {rawMode ? (
        <Textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="min-h-[240px] font-mono text-sm"
          placeholder="<p>HTML content...</p>"
        />
      ) : (
        <div
          className={cn(
            "min-h-[240px] rounded-md border border-input bg-background px-3 py-2",
            "prose prose-sm max-w-none focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2",
          )}
        >
          <EditorContent editor={editor} />
        </div>
      )}
    </div>
  );
}
