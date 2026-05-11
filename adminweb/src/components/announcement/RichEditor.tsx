import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { ImageIcon } from "lucide-react";

type Props = {
  value: string;
  onChange: (html: string) => void;
  placeholder?: string;
};

export function RichEditor({ value, onChange, placeholder }: Props) {
  const [rawMode, setRawMode] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

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

  function handleImageFile(file: File) {
    const reader = new FileReader();
    reader.onload = (e) => {
      const dataUrl = e.target?.result as string;
      const imgTag = `<img src="${dataUrl}" alt="${file.name}" style="max-width:100%;height:auto;display:block;margin:8px 0;" />`;
      if (rawMode) {
        onChange(value + imgTag);
      } else {
        // Switch to raw mode, append image, stay in raw mode so user can see it
        const newHtml = (editor?.getHTML() ?? value) + imgTag;
        onChange(newHtml);
        setRawMode(true);
      }
    };
    reader.readAsDataURL(file);
  }

  function openFilePicker() {
    fileInputRef.current?.click();
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <span className="text-sm font-medium">Content</span>
        <div className="flex items-center gap-2">
          <Button type="button" variant="outline" size="sm" onClick={openFilePicker}>
            <ImageIcon className="size-3.5 mr-1" />
            Insert Image
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={toggleMode}>
            {rawMode ? "WYSIWYG" : "Raw HTML"}
          </Button>
        </div>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        multiple
        className="hidden"
        onChange={(e) => {
          const files = Array.from(e.target.files ?? []);
          files.forEach(handleImageFile);
          e.target.value = "";
        }}
      />

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

      {rawMode && (
        <p className="text-xs text-muted-foreground">
          Images inserted via "Insert Image" are embedded as base64 data URLs.
          Switch to WYSIWYG to preview rendered content.
        </p>
      )}
    </div>
  );
}
