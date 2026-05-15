import { useEditor, EditorContent, useEditorState } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Image from "@tiptap/extension-image";
import Underline from "@tiptap/extension-underline";
import Link from "@tiptap/extension-link";
import { Table, TableRow, TableCell, TableHeader } from "@tiptap/extension-table";
import Placeholder from "@tiptap/extension-placeholder";
import { useEffect, useRef, useState } from "react";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import {
  Bold, Italic, Underline as UnderlineIcon, Strikethrough,
  List, ListOrdered, ImageIcon, Quote, Code, Code2,
  Table as TableIcon, Link as LinkIcon, Minus, Undo2, Redo2,
  ChevronDown, Trash2, Paperclip,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { uploadResourceAttachment } from "@/query/resource";
import { toast } from "sonner";

type Props = {
  value: string;
  onChange: (html: string) => void;
  placeholder?: string;
};

const HEADING_LEVELS = [1, 2, 3, 4] as const;

export function RichEditor({ value, onChange, placeholder }: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const attachmentInputRef = useRef<HTMLInputElement>(null);
  const attachmentRangeRef = useRef<{ from: number; to: number } | null>(null);
  const [rawMode, setRawMode] = useState(false);
  const [uploadingAttachment, setUploadingAttachment] = useState(false);
  const rawModeRef = useRef(false);

  const editor = useEditor({
    extensions: [
      StarterKit,
      Underline,
      Image.configure({ inline: false, allowBase64: true }),
      Link.configure({ openOnClick: false, HTMLAttributes: { rel: "noopener noreferrer", target: "_blank" } }),
      Table.configure({ resizable: false }),
      TableRow,
      TableHeader,
      TableCell,
      Placeholder.configure({ placeholder: placeholder ?? "Write your announcement…" }),
    ],
    content: value,
    onUpdate: ({ editor }) => onChange(editor.getHTML()),
  });

  useEffect(() => {
    if (!editor || editor.isFocused || rawModeRef.current) return;
    if (editor.getHTML() !== value) {
      editor.commands.setContent(value || "");
    }
  }, [value, editor]);

  function handleImageFile(file: File) {
    const reader = new FileReader();
    reader.onload = (e) => {
      editor?.chain().focus().setImage({ src: e.target?.result as string, alt: file.name }).run();
    };
    reader.readAsDataURL(file);
  }

  function promptLink() {
    const prev = editor?.getAttributes("link").href ?? "";
    const url = window.prompt("Link URL", prev);
    if (url === null) return;
    if (url === "") editor?.chain().focus().unsetLink().run();
    else editor?.chain().focus().setLink({ href: url }).run();
  }

  function openAttachmentPicker() {
    if (!editor) return;
    const { from, to } = editor.state.selection;
    if (from === to) {
      toast.error("Select the text you want to attach the file link to first.");
      return;
    }
    attachmentRangeRef.current = { from, to };
    attachmentInputRef.current?.click();
  }

  function insertAttachmentLink(href: string, range: { from: number; to: number } | null) {
    if (!editor) return;
    if (!range || range.from === range.to) return;

    const maxPos = editor.state.doc.content.size;
    const from = Math.min(Math.max(range.from, 0), maxPos);
    const to = Math.min(Math.max(range.to, from), maxPos);

    editor.chain().focus().setTextSelection({ from, to }).setLink({ href }).run();
  }

  async function handleAttachmentFiles(files: File[]) {
    if (!files.length) return;
    const initialRange = attachmentRangeRef.current;
    setUploadingAttachment(true);
    try {
      for (const [index, file] of files.entries()) {
        const attachment = await uploadResourceAttachment(file);
        insertAttachmentLink(
          attachment.url,
          index === 0 ? initialRange : null,
        );
      }
    } catch (error) {
      console.error(error);
      toast.error("Attachment upload failed. Please check the file type and try again.");
    } finally {
      attachmentRangeRef.current = null;
      setUploadingAttachment(false);
    }
  }

  function toggleRawMode() {
    if (!editor) return;
    if (rawMode) {
      rawModeRef.current = false;
      editor.commands.setContent(value);
      setRawMode(false);
    } else {
      rawModeRef.current = true;
      // Format HTML with newlines between tags so raw mode doesn't render
      // one enormous single line (which causes layout expansion and lag).
      onChange(value.replace(/></g, ">\n<"));
      setRawMode(true);
    }
  }

  function currentHeadingLabel() {
    for (const level of HEADING_LEVELS) {
      if (editor?.isActive("heading", { level })) return `H${level}`;
    }
    return "Normal";
  }

  const { isInTable } = useEditorState({
    editor,
    selector: (ctx) => ({
      isInTable: ctx.editor?.isActive("table") ?? false,
    }),
  }) ?? { isInTable: false };

  if (!editor) return null;

  const Btn = ({
    active = false, onClick, title, children, disabled = false, danger = false,
  }: {
    active?: boolean; onClick: () => void; title: string;
    children: React.ReactNode; disabled?: boolean; danger?: boolean;
  }) => (
    <button
      type="button" title={title} disabled={disabled}
      onMouseDown={(e) => { e.preventDefault(); onClick(); }}
      className={cn(
        "p-1.5 rounded transition-colors disabled:opacity-30 disabled:pointer-events-none",
        danger
          ? "text-destructive/70 hover:text-destructive hover:bg-destructive/10"
          : "text-foreground/60 hover:text-foreground hover:bg-accent",
        active && "bg-accent text-foreground",
      )}
    >
      {children}
    </button>
  );

  const Sep = () => <div className="w-px h-4 bg-border mx-0.5 self-center shrink-0" />;

  const TblBtn = ({ onClick, title, children, danger = false, disabled = false }: {
    onClick: () => void; title: string; children: React.ReactNode;
    danger?: boolean; disabled?: boolean;
  }) => (
    <button
      type="button" title={title} disabled={disabled}
      onMouseDown={(e) => { e.preventDefault(); onClick(); }}
      className={cn(
        "flex items-center gap-1 px-1.5 py-1 rounded text-xs transition-colors disabled:opacity-30 disabled:pointer-events-none",
        danger
          ? "text-destructive/70 hover:text-destructive hover:bg-destructive/10"
          : "text-foreground/60 hover:text-foreground hover:bg-accent",
      )}
    >
      {children}
    </button>
  );

  return (
    <div className="space-y-1.5">
      {/* <span className="text-sm font-medium">Content</span> */}

      <div className="rounded-lg border border-input bg-background shadow-sm overflow-hidden">

        {/* ── Main toolbar ── */}
        <div className="flex flex-wrap items-center gap-0.5 border-b bg-muted/30 px-2 py-1.5">
          {!rawMode && (
            <>
              {/* Heading */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button type="button" className="flex items-center gap-1 px-2 py-1 rounded text-xs font-medium text-foreground/70 hover:text-foreground hover:bg-accent transition-colors min-w-[72px]">
                    {currentHeadingLabel()} <ChevronDown className="size-3 opacity-60" />
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start" className="min-w-[110px]">
                  <DropdownMenuItem onSelect={() => editor.chain().focus().setParagraph().run()}>Normal</DropdownMenuItem>
                  {HEADING_LEVELS.map((level) => (
                    <DropdownMenuItem key={level} onSelect={() => editor.chain().focus().toggleHeading({ level }).run()}>
                      <span style={{ fontSize: `${1.2 - level * 0.08}rem`, fontWeight: 700 }}>Heading {level}</span>
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>

              <Sep />

              {/* Inline */}
              <Btn active={editor.isActive("bold")} onClick={() => editor.chain().focus().toggleBold().run()} title="Bold (⌘B)"><Bold className="size-3.5" /></Btn>
              <Btn active={editor.isActive("italic")} onClick={() => editor.chain().focus().toggleItalic().run()} title="Italic (⌘I)"><Italic className="size-3.5" /></Btn>
              <Btn active={editor.isActive("underline")} onClick={() => editor.chain().focus().toggleUnderline().run()} title="Underline (⌘U)"><UnderlineIcon className="size-3.5" /></Btn>
              <Btn active={editor.isActive("strike")} onClick={() => editor.chain().focus().toggleStrike().run()} title="Strikethrough"><Strikethrough className="size-3.5" /></Btn>
              <Btn active={editor.isActive("code")} onClick={() => editor.chain().focus().toggleCode().run()} title="Inline code"><Code className="size-3.5" /></Btn>
              <Btn active={editor.isActive("link")} onClick={promptLink} title="Insert / edit link"><LinkIcon className="size-3.5" /></Btn>

              <Sep />

              {/* Block */}
              <Btn active={editor.isActive("bulletList")} onClick={() => editor.chain().focus().toggleBulletList().run()} title="Bullet list"><List className="size-3.5" /></Btn>
              <Btn active={editor.isActive("orderedList")} onClick={() => editor.chain().focus().toggleOrderedList().run()} title="Numbered list"><ListOrdered className="size-3.5" /></Btn>
              <Btn active={editor.isActive("blockquote")} onClick={() => editor.chain().focus().toggleBlockquote().run()} title="Blockquote"><Quote className="size-3.5" /></Btn>
              <Btn active={editor.isActive("codeBlock")} onClick={() => editor.chain().focus().toggleCodeBlock().run()} title="Code block"><Code2 className="size-3.5" /></Btn>
              <Btn active={false} onClick={() => editor.chain().focus().setHorizontalRule().run()} title="Horizontal rule"><Minus className="size-3.5" /></Btn>

              <Sep />

              {/* Insert */}
              <button type="button" title="Insert image" onMouseDown={(e) => { e.preventDefault(); fileInputRef.current?.click(); }} className="flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors text-foreground/60 hover:text-foreground hover:bg-accent">
                <ImageIcon className="size-3.5" /> Image
              </button>
              <button type="button" title="Attach file to selected text" disabled={uploadingAttachment} onMouseDown={(e) => { e.preventDefault(); openAttachmentPicker(); }} className="flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors text-foreground/60 hover:text-foreground hover:bg-accent disabled:opacity-30 disabled:pointer-events-none">
                <Paperclip className="size-3.5" /> {uploadingAttachment ? "Uploading" : "File"}
              </button>
              <button type="button" title="Insert table" onMouseDown={(e) => { e.preventDefault(); editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run(); }} className="flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors text-foreground/60 hover:text-foreground hover:bg-accent">
                <TableIcon className="size-3.5" /> Table
              </button>

              <Sep />

              {/* History */}
              <Btn active={false} disabled={!editor.can().undo()} onClick={() => editor.chain().focus().undo().run()} title="Undo (⌘Z)"><Undo2 className="size-3.5" /></Btn>
              <Btn active={false} disabled={!editor.can().redo()} onClick={() => editor.chain().focus().redo().run()} title="Redo (⌘⇧Z)"><Redo2 className="size-3.5" /></Btn>

              <Sep />
            </>
          )}

          {/* HTML toggle */}
          <button type="button" title={rawMode ? "Switch to visual editor" : "Edit raw HTML"}
            onMouseDown={(e) => { e.preventDefault(); toggleRawMode(); }}
            className={cn("flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors", rawMode ? "bg-accent text-foreground" : "text-muted-foreground hover:text-foreground hover:bg-accent")}
          >
            <Code className="size-3.5" /> {rawMode ? "Visual" : "HTML"}
          </button>
        </div>

        {/* ── Table context toolbar (shown when cursor is inside a table) ── */}
        {isInTable && !rawMode && (
          <div className="flex flex-wrap items-center gap-0.5 border-b bg-blue-50/60 dark:bg-blue-950/20 px-2 py-1 text-xs">
            <TableIcon className="size-3 text-blue-500 mr-1 shrink-0" />
            <span className="text-blue-600 dark:text-blue-400 font-medium mr-1 shrink-0">Table:</span>

            <TblBtn onClick={() => editor.chain().focus().addColumnBefore().run()} title="Add column before">+ Col left</TblBtn>
            <TblBtn onClick={() => editor.chain().focus().addColumnAfter().run()} title="Add column after">+ Col right</TblBtn>
            <TblBtn onClick={() => editor.chain().focus().deleteColumn().run()} title="Delete column" danger>− Col</TblBtn>

            <Sep />

            <TblBtn onClick={() => editor.chain().focus().addRowBefore().run()} title="Add row above">+ Row above</TblBtn>
            <TblBtn onClick={() => editor.chain().focus().addRowAfter().run()} title="Add row below">+ Row below</TblBtn>
            <TblBtn onClick={() => editor.chain().focus().deleteRow().run()} title="Delete row" danger>− Row</TblBtn>

            <Sep />

            <TblBtn onClick={() => editor.chain().focus().toggleHeaderRow().run()} title="Toggle header row">Header row</TblBtn>
            <TblBtn onClick={() => editor.chain().focus().toggleHeaderColumn().run()} title="Toggle header column">Header col</TblBtn>

            <Sep />

            <TblBtn onClick={() => editor.chain().focus().deleteTable().run()} title="Delete table" danger>
              <Trash2 className="size-3" /> Delete table
            </TblBtn>
          </div>
        )}

        {/* ── Editor / Raw area ── */}
        {rawMode ? (
          <Textarea value={value} onChange={(e) => onChange(e.target.value)}
            className="min-h-[320px] rounded-none border-0 font-mono text-sm focus-visible:ring-0 resize-none overflow-x-hidden break-all"
            placeholder="<p>HTML content…</p>"
          />
        ) : (
          <div className={cn(
            "min-h-[320px] px-5 py-4 prose prose-sm max-w-none",
            "[&_.ProseMirror]:outline-none [&_.ProseMirror]:min-h-[280px]",
            "[&_.ProseMirror_p.is-editor-empty:first-child::before]:text-muted-foreground",
            "[&_.ProseMirror_p.is-editor-empty:first-child::before]:content-[attr(data-placeholder)]",
            "[&_.ProseMirror_p.is-editor-empty:first-child::before]:float-left",
            "[&_.ProseMirror_p.is-editor-empty:first-child::before]:pointer-events-none",
            "[&_.ProseMirror_img]:max-w-full [&_.ProseMirror_img]:rounded-md [&_.ProseMirror_img]:my-3",
            "[&_.ProseMirror_a]:text-primary [&_.ProseMirror_a]:underline [&_.ProseMirror_a]:underline-offset-2",
            "[&_.ProseMirror_hr]:my-4 [&_.ProseMirror_hr]:border-border",
            // table
            "[&_.ProseMirror_.tableWrapper]:overflow-x-auto",
            "[&_.ProseMirror_table]:border-collapse [&_.ProseMirror_table]:my-3 [&_.ProseMirror_table]:w-full",
            "[&_.ProseMirror_th]:border [&_.ProseMirror_th]:border-border [&_.ProseMirror_th]:px-3 [&_.ProseMirror_th]:py-2 [&_.ProseMirror_th]:bg-muted [&_.ProseMirror_th]:font-semibold [&_.ProseMirror_th]:text-left [&_.ProseMirror_th]:text-sm [&_.ProseMirror_th]:min-w-[80px]",
            "[&_.ProseMirror_td]:border [&_.ProseMirror_td]:border-border [&_.ProseMirror_td]:px-3 [&_.ProseMirror_td]:py-2 [&_.ProseMirror_td]:text-sm [&_.ProseMirror_td]:min-w-[80px]",
            "[&_.ProseMirror_.selectedCell]:!bg-primary/10",
          )}>
            <EditorContent editor={editor} />
          </div>
        )}
      </div>

      <input ref={fileInputRef} type="file" accept="image/*" multiple className="hidden"
        onChange={(e) => { Array.from(e.target.files ?? []).forEach(handleImageFile); e.target.value = ""; }}
      />
      <input ref={attachmentInputRef} type="file" multiple className="hidden"
        onChange={(e) => { void handleAttachmentFiles(Array.from(e.target.files ?? [])); e.target.value = ""; }}
      />
    </div>
  );
}
