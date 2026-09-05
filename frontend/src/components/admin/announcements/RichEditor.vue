<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Image from '@tiptap/extension-image'
import Underline from '@tiptap/extension-underline'
import Link from '@tiptap/extension-link'
import { Table, TableRow, TableHeader, TableCell } from '@tiptap/extension-table'
import Placeholder from '@tiptap/extension-placeholder'
import { uploadLinkedResourceAttachment } from '@/utils/adminAPI'

interface Props {
  modelValue?: string
  placeholder?: string
  readOnly?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: '',
  placeholder: 'Write your announcement…',
  readOnly: false
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'change', value: string): void
}>()

const fileInputRef = ref<HTMLInputElement | null>(null)
const attachmentInputRef = ref<HTMLInputElement | null>(null)
const attachmentRange = ref<{ from: number; to: number } | null>(null)
const rawMode = ref(false)
const rawHtml = ref(props.modelValue || '')
const uploadingAttachment = ref(false)
const attachmentError = ref<string | null>(null)
const showHeadingDropdown = ref(false)

const updateTick = ref(0)

const editor = useEditor({
  extensions: [
    StarterKit.configure({
      link: false,
      underline: false
    }),
    Underline,
    Image.configure({ inline: false, allowBase64: true }),
    Link.configure({
      openOnClick: props.readOnly,
      HTMLAttributes: { rel: 'noopener noreferrer', target: '_blank' }
    }),
    Table.configure({ resizable: false }),
    TableRow,
    TableHeader,
    TableCell,
    Placeholder.configure({
      placeholder: props.placeholder
    })
  ],
  content: props.modelValue,
  editable: !props.readOnly,
  onUpdate: ({ editor: ed }) => {
    if (!props.readOnly && !rawMode.value) {
      const html = ed.getHTML()
      rawHtml.value = html
      emit('update:modelValue', html)
      emit('change', html)
    }
  },
  onTransaction: () => {
    updateTick.value++
  }
})

watch(
  () => props.modelValue,
  (newVal) => {
    if (rawMode.value) {
      rawHtml.value = newVal || ''
      return
    }
    if (!editor.value || editor.value.isFocused) return
    const currentHTML = editor.value.getHTML()
    if (currentHTML !== newVal) {
      editor.value.commands.setContent(newVal || '', { emitUpdate: false })
      rawHtml.value = newVal || ''
    }
  }
)

watch(
  () => props.readOnly,
  (isReadOnly) => {
    if (!editor.value) return
    editor.value.setEditable(!isReadOnly)
    if (isReadOnly && rawMode.value) {
      rawMode.value = false
    }
  }
)

onBeforeUnmount(() => {
  editor.value?.destroy()
})

const HEADING_LEVELS = [1, 2, 3, 4] as const

const currentHeadingLabel = computed(() => {
  void updateTick.value
  if (!editor.value) return 'Normal'
  for (const level of HEADING_LEVELS) {
    if (editor.value.isActive('heading', { level })) return `H${level}`
  }
  return 'Normal'
})

const isInTable = computed(() => {
  void updateTick.value
  return editor.value?.isActive('table') ?? false
})

const canUndo = computed(() => {
  void updateTick.value
  return editor.value?.can().undo() ?? false
})

const canRedo = computed(() => {
  void updateTick.value
  return editor.value?.can().redo() ?? false
})

function isActive(name: string, opts?: Record<string, unknown>): boolean {
  void updateTick.value
  return editor.value?.isActive(name, opts) ?? false
}

function selectHeading(level: number | 0) {
  if (!editor.value) return
  if (level === 0) {
    editor.value.chain().focus().setParagraph().run()
  } else {
    editor.value.chain().focus().toggleHeading({ level: level as 1 | 2 | 3 | 4 }).run()
  }
  showHeadingDropdown.value = false
}

function promptLink() {
  if (!editor.value) return
  const prev = (editor.value.getAttributes('link').href as string) || ''
  const url = window.prompt('Link URL', prev)
  if (url === null) return
  if (url.trim() === '') {
    editor.value.chain().focus().unsetLink().run()
  } else {
    editor.value.chain().focus().setLink({ href: url.trim() }).run()
  }
}

function handleImageFile(file: File) {
  const reader = new FileReader()
  reader.onload = (e) => {
    editor.value
      ?.chain()
      .focus()
      .setImage({ src: e.target?.result as string, alt: file.name })
      .run()
  }
  reader.readAsDataURL(file)
}

function openAttachmentPicker() {
  if (!editor.value) return
  const { from, to } = editor.value.state.selection
  if (from === to) {
    attachmentError.value = 'Please select the text you want to attach the file link to first.'
    setTimeout(() => {
      attachmentError.value = null
    }, 4000)
    return
  }
  attachmentRange.value = { from, to }
  attachmentInputRef.value?.click()
}

function insertAttachmentLink(href: string, range: { from: number; to: number } | null) {
  if (!editor.value) return
  if (!range || range.from === range.to) return

  const maxPos = editor.value.state.doc.content.size
  const from = Math.min(Math.max(range.from, 0), maxPos)
  const to = Math.min(Math.max(range.to, from), maxPos)

  editor.value.chain().focus().setTextSelection({ from, to }).setLink({ href }).run()
}

async function handleAttachmentFiles(files: File[]) {
  if (!files.length) return
  const initialRange = attachmentRange.value
  uploadingAttachment.value = true
  attachmentError.value = null
  try {
    for (const [index, file] of files.entries()) {
      const resource = await uploadLinkedResourceAttachment(file)
      insertAttachmentLink(resource.accessUrl || resource.downloadUrl, index === 0 ? initialRange : null)
    }
  } catch (err: unknown) {
    console.error('Attachment upload failed:', err)
    attachmentError.value = err instanceof Error ? err.message : 'Attachment upload failed. Please try again.'
  } finally {
    attachmentRange.value = null
    uploadingAttachment.value = false
  }
}

function toggleRawMode() {
  if (!editor.value) return
  if (rawMode.value) {
    rawMode.value = false
    editor.value.commands.setContent(rawHtml.value || '')
    emit('update:modelValue', rawHtml.value)
    emit('change', rawHtml.value)
  } else {
    rawMode.value = true
    const current = editor.value.getHTML()
    rawHtml.value = current.replace(/></g, '>\n<')
    emit('update:modelValue', rawHtml.value)
    emit('change', rawHtml.value)
  }
}

function handleRawInput(e: Event) {
  const target = e.target as HTMLTextAreaElement
  rawHtml.value = target.value
  emit('update:modelValue', target.value)
  emit('change', target.value)
}
</script>

<template>
  <div class="rich-editor-wrapper">
    <!-- Attachment Error Banner -->
    <div v-if="attachmentError" class="rich-editor-alert">
      <i class="fas fa-circle-exclamation mr-1.5"></i>
      <span>{{ attachmentError }}</span>
      <button type="button" class="close-alert-btn" @click="attachmentError = null">×</button>
    </div>

    <div class="rich-editor-container">
      <!-- Main Toolbar -->
      <div v-if="!readOnly" class="rich-editor-toolbar">
        <template v-if="!rawMode">
          <!-- Heading Dropdown -->
          <div class="heading-dropdown-container">
            <button
              type="button"
              class="toolbar-btn heading-btn"
              :title="`Current style: ${currentHeadingLabel}`"
              @click="showHeadingDropdown = !showHeadingDropdown"
            >
              <span>{{ currentHeadingLabel }}</span>
              <i class="fas fa-chevron-down heading-chevron"></i>
            </button>
            <div v-if="showHeadingDropdown" class="heading-dropdown-menu">
              <button
                type="button"
                class="dropdown-item"
                :class="{ active: currentHeadingLabel === 'Normal' }"
                @click="selectHeading(0)"
              >
                Normal
              </button>
              <button
                type="button"
                class="dropdown-item h1-item"
                :class="{ active: currentHeadingLabel === 'H1' }"
                @click="selectHeading(1)"
              >
                Heading 1
              </button>
              <button
                type="button"
                class="dropdown-item h2-item"
                :class="{ active: currentHeadingLabel === 'H2' }"
                @click="selectHeading(2)"
              >
                Heading 2
              </button>
              <button
                type="button"
                class="dropdown-item h3-item"
                :class="{ active: currentHeadingLabel === 'H3' }"
                @click="selectHeading(3)"
              >
                Heading 3
              </button>
              <button
                type="button"
                class="dropdown-item h4-item"
                :class="{ active: currentHeadingLabel === 'H4' }"
                @click="selectHeading(4)"
              >
                Heading 4
              </button>
            </div>
          </div>

          <div class="toolbar-sep"></div>

          <!-- Inline Styles -->
          <button
            type="button"
            class="toolbar-btn icon-btn"
            :class="{ active: isActive('bold') }"
            title="Bold (Ctrl/Cmd+B)"
            @mousedown.prevent="editor?.chain().focus().toggleBold().run()"
          >
            <i class="fas fa-bold"></i>
          </button>
          <button
            type="button"
            class="toolbar-btn icon-btn"
            :class="{ active: isActive('italic') }"
            title="Italic (Ctrl/Cmd+I)"
            @mousedown.prevent="editor?.chain().focus().toggleItalic().run()"
          >
            <i class="fas fa-italic"></i>
          </button>
          <button
            type="button"
            class="toolbar-btn icon-btn"
            :class="{ active: isActive('underline') }"
            title="Underline (Ctrl/Cmd+U)"
            @mousedown.prevent="editor?.chain().focus().toggleUnderline().run()"
          >
            <i class="fas fa-underline"></i>
          </button>
          <button
            type="button"
            class="toolbar-btn icon-btn"
            :class="{ active: isActive('strike') }"
            title="Strikethrough"
            @mousedown.prevent="editor?.chain().focus().toggleStrike().run()"
          >
            <i class="fas fa-strikethrough"></i>
          </button>
          <button
            type="button"
            class="toolbar-btn icon-btn"
            :class="{ active: isActive('code') }"
            title="Inline code"
            @mousedown.prevent="editor?.chain().focus().toggleCode().run()"
          >
            <i class="fas fa-code"></i>
          </button>
          <button
            type="button"
            class="toolbar-btn icon-btn"
            :class="{ active: isActive('link') }"
            title="Insert / edit link"
            @mousedown.prevent="promptLink"
          >
            <i class="fas fa-link"></i>
          </button>

          <div class="toolbar-sep"></div>

          <!-- Block Styles -->
          <button
            type="button"
            class="toolbar-btn icon-btn"
            :class="{ active: isActive('bulletList') }"
            title="Bullet list"
            @mousedown.prevent="editor?.chain().focus().toggleBulletList().run()"
          >
            <i class="fas fa-list-ul"></i>
          </button>
          <button
            type="button"
            class="toolbar-btn icon-btn"
            :class="{ active: isActive('orderedList') }"
            title="Numbered list"
            @mousedown.prevent="editor?.chain().focus().toggleOrderedList().run()"
          >
            <i class="fas fa-list-ol"></i>
          </button>
          <button
            type="button"
            class="toolbar-btn icon-btn"
            :class="{ active: isActive('blockquote') }"
            title="Blockquote"
            @mousedown.prevent="editor?.chain().focus().toggleBlockquote().run()"
          >
            <i class="fas fa-quote-left"></i>
          </button>
          <button
            type="button"
            class="toolbar-btn icon-btn"
            :class="{ active: isActive('codeBlock') }"
            title="Code block"
            @mousedown.prevent="editor?.chain().focus().toggleCodeBlock().run()"
          >
            <i class="fas fa-file-code"></i>
          </button>
          <button
            type="button"
            class="toolbar-btn icon-btn"
            title="Horizontal rule"
            @mousedown.prevent="editor?.chain().focus().setHorizontalRule().run()"
          >
            <i class="fas fa-minus"></i>
          </button>

          <div class="toolbar-sep"></div>

          <!-- Insert Actions -->
          <button
            type="button"
            class="toolbar-btn text-icon-btn"
            title="Insert image"
            @mousedown.prevent="fileInputRef?.click()"
          >
            <i class="fas fa-image"></i>
            <span>Image</span>
          </button>
          <button
            type="button"
            class="toolbar-btn text-icon-btn"
            title="Attach file to selected text"
            :disabled="uploadingAttachment"
            @mousedown.prevent="openAttachmentPicker"
          >
            <i class="fas fa-paperclip"></i>
            <span>{{ uploadingAttachment ? 'Uploading…' : 'File' }}</span>
          </button>
          <button
            type="button"
            class="toolbar-btn text-icon-btn"
            title="Insert table (3x3)"
            @mousedown.prevent="editor?.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()"
          >
            <i class="fas fa-table"></i>
            <span>Table</span>
          </button>

          <div class="toolbar-sep"></div>

          <!-- History -->
          <button
            type="button"
            class="toolbar-btn icon-btn"
            :disabled="!canUndo"
            title="Undo (Ctrl/Cmd+Z)"
            @mousedown.prevent="editor?.chain().focus().undo().run()"
          >
            <i class="fas fa-rotate-left"></i>
          </button>
          <button
            type="button"
            class="toolbar-btn icon-btn"
            :disabled="!canRedo"
            title="Redo (Ctrl/Cmd+Y / Shift+Cmd+Z)"
            @mousedown.prevent="editor?.chain().focus().redo().run()"
          >
            <i class="fas fa-rotate-right"></i>
          </button>

          <div class="toolbar-sep"></div>
        </template>

        <!-- Raw HTML Toggle Button -->
        <button
          type="button"
          class="toolbar-btn text-icon-btn toggle-raw-btn"
          :class="{ active: rawMode }"
          :title="rawMode ? 'Switch to visual editor' : 'Edit raw HTML'"
          @mousedown.prevent="toggleRawMode"
        >
          <i class="fas fa-code"></i>
          <span>{{ rawMode ? 'Visual' : 'HTML' }}</span>
        </button>
      </div>

      <!-- Table Context Toolbar -->
      <div v-if="isInTable && !rawMode && !readOnly" class="table-context-bar">
        <div class="table-context-heading">
          <i class="fas fa-table text-blue-500"></i>
          <span class="table-context-title">Table:</span>
        </div>

        <button
          type="button"
          class="table-action-btn"
          title="Add column before"
          @mousedown.prevent="editor?.chain().focus().addColumnBefore().run()"
        >
          + Col left
        </button>
        <button
          type="button"
          class="table-action-btn"
          title="Add column after"
          @mousedown.prevent="editor?.chain().focus().addColumnAfter().run()"
        >
          + Col right
        </button>
        <button
          type="button"
          class="table-action-btn danger"
          title="Delete column"
          @mousedown.prevent="editor?.chain().focus().deleteColumn().run()"
        >
          − Col
        </button>

        <div class="toolbar-sep"></div>

        <button
          type="button"
          class="table-action-btn"
          title="Add row above"
          @mousedown.prevent="editor?.chain().focus().addRowBefore().run()"
        >
          + Row above
        </button>
        <button
          type="button"
          class="table-action-btn"
          title="Add row below"
          @mousedown.prevent="editor?.chain().focus().addRowAfter().run()"
        >
          + Row below
        </button>
        <button
          type="button"
          class="table-action-btn danger"
          title="Delete row"
          @mousedown.prevent="editor?.chain().focus().deleteRow().run()"
        >
          − Row
        </button>

        <div class="toolbar-sep"></div>

        <button
          type="button"
          class="table-action-btn"
          title="Toggle header row"
          @mousedown.prevent="editor?.chain().focus().toggleHeaderRow().run()"
        >
          Header row
        </button>
        <button
          type="button"
          class="table-action-btn"
          title="Toggle header column"
          @mousedown.prevent="editor?.chain().focus().toggleHeaderColumn().run()"
        >
          Header col
        </button>

        <div class="toolbar-sep"></div>

        <button
          type="button"
          class="table-action-btn danger table-action-btn--delete"
          title="Delete table"
          @mousedown.prevent="editor?.chain().focus().deleteTable().run()"
        >
          <i class="fas fa-trash-can"></i>
          <span>Delete table</span>
        </button>
      </div>

      <!-- Editor Content Area / Raw HTML Textarea -->
      <div v-if="rawMode" class="rich-editor-raw-area">
        <textarea
          :value="rawHtml"
          class="raw-html-textarea"
          placeholder="<p>HTML content…</p>"
          @input="handleRawInput"
        ></textarea>
      </div>
      <div v-else class="rich-editor-content-area">
        <EditorContent :editor="editor" />
      </div>
    </div>

    <!-- Hidden file inputs -->
    <input
      ref="fileInputRef"
      type="file"
      accept="image/*"
      multiple
      class="hidden-input"
      @change="(e: Event) => {
        const target = e.target as HTMLInputElement
        Array.from(target.files ?? []).forEach(handleImageFile)
        target.value = ''
      }"
    />
    <input
      ref="attachmentInputRef"
      type="file"
      multiple
      class="hidden-input"
      @change="(e: Event) => {
        const target = e.target as HTMLInputElement
        void handleAttachmentFiles(Array.from(target.files ?? []))
        target.value = ''
      }"
    />
  </div>
</template>

<style scoped>
.rich-editor-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  width: 100%;
}

.rich-editor-alert {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  font-size: 0.8125rem;
  color: #b91c1c;
  background-color: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 0.375rem;
}

.close-alert-btn {
  margin-left: auto;
  font-size: 1.125rem;
  line-height: 1;
  background: none;
  border: none;
  cursor: pointer;
  color: #b91c1c;
}

.rich-editor-container {
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  background-color: #ffffff;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  overflow: hidden;
  transition: border-color 0.15s ease-in-out;
}

.rich-editor-container:focus-within {
  border-color: #2563eb;
}

.rich-editor-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.25rem;
  padding: 0.375rem 0.5rem;
  border-bottom: 1px solid #e5e7eb;
  background-color: #f9fafb;
}

.heading-dropdown-container {
  position: relative;
}

.toolbar-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: 0.25rem;
  padding: 0.375rem 0.5rem;
  font-size: 0.8125rem;
  font-weight: 500;
  color: #4b5563;
  cursor: pointer;
  transition: all 0.15s ease;
}

.toolbar-btn:hover:not(:disabled) {
  background-color: #e5e7eb;
  color: #111827;
}

.toolbar-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.toolbar-btn.active {
  background-color: #e0e7ff;
  color: #2563eb;
}

.toolbar-btn.icon-btn {
  width: 1.875rem;
  height: 1.875rem;
  padding: 0;
}

.toolbar-btn.text-icon-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.35rem 0.625rem;
  font-size: 0.8125rem;
}

.toolbar-btn.text-icon-btn i {
  font-size: 0.8125rem;
}

.heading-btn {
  min-width: 5.5rem;
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.375rem 0.625rem;
}

.heading-chevron {
  font-size: 0.6875rem;
  margin-left: 0.35rem;
  opacity: 0.7;
}

.heading-dropdown-menu {
  position: absolute;
  top: 100%;
  left: 0;
  z-index: 50;
  margin-top: 0.25rem;
  min-width: 8rem;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 0.375rem;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
  padding: 0.25rem;
  display: flex;
  flex-direction: column;
}

.dropdown-item {
  width: 100%;
  text-align: left;
  padding: 0.375rem 0.625rem;
  font-size: 0.8125rem;
  border: none;
  border-radius: 0.25rem;
  background: transparent;
  color: #374151;
  cursor: pointer;
}

.dropdown-item:hover {
  background-color: #f3f4f6;
  color: #111827;
}

.dropdown-item.active {
  background-color: #eff6ff;
  color: #2563eb;
  font-weight: 600;
}

.h1-item {
  font-size: 1.125rem;
  font-weight: 700;
}

.h2-item {
  font-size: 1rem;
  font-weight: 700;
}

.h3-item {
  font-size: 0.875rem;
  font-weight: 600;
}

.h4-item {
  font-size: 0.8125rem;
  font-weight: 600;
}

.toolbar-sep {
  width: 1px;
  height: 1rem;
  background-color: #d1d5db;
  margin: 0 0.25rem;
  align-self: center;
}

.toggle-raw-btn {
  margin-left: auto;
  font-size: 0.75rem;
  padding: 0.25rem 0.5rem;
}

.table-context-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.45rem;
  padding: 0.35rem 0.625rem;
  background-color: #eff6ff;
  border-bottom: 1px solid #bfdbfe;
  font-size: 0.8125rem;
}

.table-context-heading {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  color: #2563eb;
  font-weight: 600;
  margin-right: 0.25rem;
}

.table-context-title {
  color: #2563eb;
  font-weight: 600;
}

.table-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.25rem 0.45rem;
  border: none;
  border-radius: 0.25rem;
  background: transparent;
  font-size: 0.78125rem;
  color: #1e40af;
  cursor: pointer;
  transition: all 0.15s ease;
}

.table-action-btn:hover {
  background-color: #dbeafe;
}

.table-action-btn.danger {
  color: #dc2626;
}

.table-action-btn.danger:hover {
  background-color: #fee2e2;
}

.table-action-btn--delete {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

.rich-editor-content-area {
  min-height: 20rem;
  padding: 1rem 1.25rem;
}

.rich-editor-raw-area {
  width: 100%;
}

.raw-html-textarea {
  width: 100%;
  min-height: 20rem;
  padding: 1rem 1.25rem;
  border: none;
  outline: none;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.8125rem;
  line-height: 1.5;
  color: #1f2937;
  resize: vertical;
  background-color: transparent;
}

.hidden-input {
  display: none;
}
</style>

<style>
/* TipTap ProseMirror content styling */
.rich-editor-content-area .tiptap.ProseMirror {
  outline: none;
  min-height: 18rem;
  font-size: 0.875rem;
  line-height: 1.625;
  color: #1f2937;
}

.rich-editor-content-area .tiptap.ProseMirror p.is-editor-empty:first-child::before {
  content: attr(data-placeholder);
  color: #9ca3af;
  float: left;
  pointer-events: none;
  height: 0;
}

.rich-editor-content-area .tiptap.ProseMirror h1 {
  font-size: 1.5rem;
  font-weight: 700;
  margin-top: 1.25rem;
  margin-bottom: 0.5rem;
  color: #111827;
}

.rich-editor-content-area .tiptap.ProseMirror h2 {
  font-size: 1.25rem;
  font-weight: 700;
  margin-top: 1rem;
  margin-bottom: 0.5rem;
  color: #111827;
}

.rich-editor-content-area .tiptap.ProseMirror h3 {
  font-size: 1.125rem;
  font-weight: 600;
  margin-top: 0.875rem;
  margin-bottom: 0.375rem;
  color: #111827;
}

.rich-editor-content-area .tiptap.ProseMirror h4 {
  font-size: 1rem;
  font-weight: 600;
  margin-top: 0.75rem;
  margin-bottom: 0.25rem;
  color: #111827;
}

.rich-editor-content-area .tiptap.ProseMirror p {
  margin-top: 0.5rem;
  margin-bottom: 0.5rem;
}

.rich-editor-content-area .tiptap.ProseMirror ul {
  list-style-type: disc;
  padding-left: 1.5rem;
  margin-top: 0.5rem;
  margin-bottom: 0.5rem;
}

.rich-editor-content-area .tiptap.ProseMirror ol {
  list-style-type: decimal;
  padding-left: 1.5rem;
  margin-top: 0.5rem;
  margin-bottom: 0.5rem;
}

.rich-editor-content-area .tiptap.ProseMirror blockquote {
  border-left: 4px solid #d1d5db;
  padding-left: 1rem;
  margin: 0.75rem 0;
  font-style: italic;
  color: #4b5563;
}

.rich-editor-content-area .tiptap.ProseMirror code {
  background-color: #f3f4f6;
  color: #2563eb;
  padding: 0.125rem 0.25rem;
  border-radius: 0.25rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.8125rem;
}

.rich-editor-content-area .tiptap.ProseMirror pre {
  background-color: #1f2937;
  color: #f9fafb;
  padding: 0.75rem 1rem;
  border-radius: 0.375rem;
  margin: 0.75rem 0;
  overflow-x: auto;
}

.rich-editor-content-area .tiptap.ProseMirror pre code {
  background-color: transparent;
  color: inherit;
  padding: 0;
}

.rich-editor-content-area .tiptap.ProseMirror hr {
  margin: 1rem 0;
  border: none;
  border-top: 1px solid #e5e7eb;
}

.rich-editor-content-area .tiptap.ProseMirror img {
  max-width: 100%;
  border-radius: 0.375rem;
  margin: 0.75rem 0;
}

.rich-editor-content-area .tiptap.ProseMirror a {
  color: #2563eb;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.rich-editor-content-area .tiptap.ProseMirror .tableWrapper {
  overflow-x: auto;
  margin: 0.75rem 0;
}

.rich-editor-content-area .tiptap.ProseMirror table {
  width: 100%;
  border-collapse: collapse;
}

.rich-editor-content-area .tiptap.ProseMirror th {
  border: 1px solid #d1d5db;
  padding: 0.5rem 0.75rem;
  background-color: #f3f4f6;
  font-weight: 600;
  text-align: left;
  min-width: 5rem;
}

.rich-editor-content-area .tiptap.ProseMirror td {
  border: 1px solid #d1d5db;
  padding: 0.5rem 0.75rem;
  min-width: 5rem;
}

.rich-editor-content-area .tiptap.ProseMirror .selectedCell {
  background-color: #dbeafe !important;
}
</style>
