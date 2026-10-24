<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Image from '@tiptap/extension-image'
import { Table, TableRow, TableHeader, TableCell } from '@tiptap/extension-table'
import Placeholder from '@tiptap/extension-placeholder'
import { uploadLinkedResourceAttachment } from '@/utils/adminAPI'
import { BOX_LOOKS, BUTTON_LOOKS, EmailBox, EmailButton, lookOf, swatchOf } from './emailBlocks'
import { EmailTable, EmailTableCell, EmailTableHeader } from './emailTables'
import {
  EmailTextStyle,
  EmailTextStyles,
  TEXT_GAPS,
  TEXT_SIZES,
  gapBelowSelection,
  hasGapTarget,
  styleValue,
  textStyleAt
} from './emailTextStyle'
import { FontFamily, FONT_STYLES, type AllowedFont } from './fontFamilyExtension'
import {
  TextColor,
  COLOR_SECTIONS,
  normalizeAllowedColor,
  type AllowedColorHex
} from './textColorExtension'
import LinkDialog from './LinkDialog.vue'
import ConfirmDialog from './ConfirmDialog.vue'
import { formatHtml, visualLosses } from './emailHtml'

interface Props {
  modelValue?: string
  placeholder?: string
  readOnly?: boolean
  /**
   * Email bodies are sanitised server-side with nh3, which strips base64
   * images, `data:` URLs and uploaded-file links. Hiding those insert tools
   * keeps the editor honest about what will actually survive a save. Tables
   * do survive, drawn with lines and padding the server keeps.
   */
  emailMode?: boolean
  /** Tighter vertical rhythm for side-by-side editor/preview layouts. */
  compact?: boolean
  /** Email mode: the email's link placeholders, offered in the link dialog. */
  linkPlaceholders?: string[]
  /** Whether the toolbar exposes uploaded-file attachments. */
  allowAttachments?: boolean
  /** Whether the toolbar exposes the manual insert/edit-link dialog. */
  allowManualLinks?: boolean
}

// Inline code in an email, as the editor shows it.
const EMAIL_CODE_STYLE =
  'background-color:#f3f4f6; color:#1a2e23; padding:2px 4px; border-radius:4px; ' +
  "font-family:Menlo, Consolas, 'Courier New', monospace; font-size:13px"

const props = withDefaults(defineProps<Props>(), {
  modelValue: '',
  placeholder: undefined,
  readOnly: false,
  emailMode: false,
  compact: false,
  linkPlaceholders: () => [],
  allowAttachments: true,
  allowManualLinks: true
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'update:needsOversizeAck', value: boolean): void
  (e: 'change', value: string): void
  (e: 'focus'): void
}>()

const resolvedPlaceholder = computed(
  () => props.placeholder ?? (props.emailMode ? 'Write your email…' : 'Write your announcement…')
)

const LARGE_FILE_BYTES = 25 * 1024 * 1024

const fileInputRef = ref<HTMLInputElement | null>(null)
const attachmentInputRef = ref<HTMLInputElement | null>(null)
const attachmentRange = ref<{ from: number; to: number } | null>(null)
const pendingAttachmentFiles = ref<File[]>([])
const pendingAttachmentRange = ref<{ from: number; to: number } | null>(null)
const oversizedAttachmentFile = ref<File | null>(null)
const acknowledgedOversizedAttachment = ref(false)
const rawMode = ref(false)
const rawHtml = ref(props.modelValue || '')
// Whether the visual view has changed the content since it came in: until
// then rawHtml is exactly the HTML it was given, which the HTML view shows.
const visualEdited = ref(false)
// A switch to the visual view waiting on the admin, and what it would drop.
const visualSwitch = ref<{ open: boolean; losses: string[] }>({ open: false, losses: [] })
const uploadingAttachment = ref(false)
const attachmentError = ref<string | null>(null)
const showHeadingDropdown = ref(false)
const showFontDropdown = ref(false)
const showColorDropdown = ref(false)
const selectedFont = ref<AllowedFont>('Arial')
const selectedColor = ref<AllowedColorHex>('#000000')

const updateTick = ref(0)

const editor = useEditor({
  extensions: [
    StarterKit.configure({
      // No code blocks: neither emails nor announcements use them.
      codeBlock: false,
      // In emails inline code carries its own look, since email apps ignore
      // the editor's stylesheet; the server keeps it.
      ...(props.emailMode ? { code: { HTMLAttributes: { style: EMAIL_CODE_STYLE } } } : {}),
      link: {
        openOnClick: props.readOnly,
        HTMLAttributes: { rel: 'noopener noreferrer', target: '_blank' }
      }
    }),
    FontFamily,
    ...(!props.emailMode ? [TextColor] : []),
    Image.configure({ inline: false, allowBase64: true }),
    // In emails a table draws its own lines, since email clients ignore the
    // page's stylesheet, or none for a template's layout (emailTables.ts).
    ...(props.emailMode
      ? [EmailTable.configure({ resizable: false }), TableRow, EmailTableHeader, EmailTableCell]
      : [Table.configure({ resizable: false }), TableRow, TableHeader, TableCell]),
    Placeholder.configure({
      placeholder: resolvedPlaceholder.value
    }),
    // The boxes and buttons of the emails' built-in design, in every editor.
    EmailBox,
    EmailButton,
    // Every editor keeps its text's colours, sizes and spacing.
    EmailTextStyle,
    EmailTextStyles
  ],
  content: props.modelValue,
  editable: !props.readOnly,
  onUpdate: ({ editor: ed }) => {
    if (!props.readOnly && !rawMode.value) {
      const html = ed.getHTML()
      rawHtml.value = html
      visualEdited.value = true
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
      visualEdited.value = false
    }
  }
)

watch(
  () => props.readOnly,
  (isReadOnly) => {
    if (!editor.value) return
    editor.value.setEditable(!isReadOnly)
  }
)

onMounted(() => {
  document.addEventListener('click', onDocumentClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick)
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

const currentFontLabel = computed<AllowedFont>(() => {
  void updateTick.value
  if (!editor.value) return selectedFont.value
  const fontAttr = editor.value.getAttributes('fontFamily')?.fontFamily
  if (fontAttr === 'Times New Roman') return 'Times New Roman'
  if (fontAttr === 'Arial') return 'Arial'
  if (editor.value.isActive('fontFamily')) {
    return selectedFont.value
  }
  return 'Arial'
})

const currentFontFamilyStyle = computed(() => {
  return FONT_STYLES[currentFontLabel.value] || 'inherit'
})

function selectFont(font: AllowedFont) {
  if (!editor.value) return
  selectedFont.value = font
  editor.value.chain().focus().setFontFamily(font).run()
  showFontDropdown.value = false
}

const currentTextColor = computed<AllowedColorHex>(() => {
  void updateTick.value
  if (!editor.value) return selectedColor.value
  const rawColor = props.emailMode
    ? shownColour.value
    : editor.value.getAttributes('textColor')?.color
  const normalized = normalizeAllowedColor(rawColor)
  if (normalized) return normalized
  if (!props.emailMode && editor.value.isActive('textColor')) {
    return selectedColor.value
  }
  return '#000000'
})

const colorMenuOnRight = ref(false)

function toggleColorDropdown(event: MouseEvent) {
  if (showColorDropdown.value) {
    showColorDropdown.value = false
    return
  }
  const target = event.currentTarget as HTMLElement
  const button = target.getBoundingClientRect()
  const toolbar = target.closest('.rich-editor-toolbar')?.getBoundingClientRect()
  colorMenuOnRight.value = !!toolbar && button.left + 280 > toolbar.right
  showHeadingDropdown.value = false
  showFontDropdown.value = false
  emailMenu.value = null
  showColorDropdown.value = true
}

function selectColor(color: AllowedColorHex) {
  if (!editor.value) return
  selectedColor.value = color
  if (props.emailMode) {
    editor.value.chain().focus().setTextColour(color).run()
  } else {
    editor.value.chain().focus().setTextColor(color).run()
  }
  showColorDropdown.value = false
}

function onDocumentClick(e: MouseEvent) {
  const target = e.target as HTMLElement | null
  if (!target) return
  if (!target.closest('.heading-dropdown-container')) {
    showHeadingDropdown.value = false
    showFontDropdown.value = false
    showColorDropdown.value = false
    emailMenu.value = null
  }
}

const isInTable = computed(() => {
  void updateTick.value
  return editor.value?.isActive('table') ?? false
})

/** Whether the table the cursor is in draws its lines (email mode). */
const tableHasLines = computed(() => {
  void updateTick.value
  return editor.value?.getAttributes('table').lines !== false
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
  showFontDropdown.value = false
  showColorDropdown.value = false
}

// -- Link dialog: text links, and email buttons -------------------------------

const linkDialog = ref({ open: false, kind: 'link' as 'link' | 'button', adding: true, link: '', style: '' })

/** Link the selected text, or change or remove the link the cursor is in. */
function editLink() {
  if (!editor.value) return
  const link = (editor.value.getAttributes('link').href as string) || ''
  linkDialog.value = { open: true, kind: 'link', adding: !link, link, style: '' }
}

function onLinkChosen(href: string) {
  if (!editor.value) return
  const { kind, adding, style } = linkDialog.value
  const chain = editor.value.chain().focus()
  if (kind === 'button') {
    chain.setEmailButton(adding ? { href, style } : { href }).run()
  } else if (editor.value.state.selection.empty && !editor.value.isActive('link')) {
    // Nothing selected: the link itself becomes the text.
    chain.insertContent({ type: 'text', text: href, marks: [{ type: 'link', attrs: { href } }] }).run()
  } else {
    chain.extendMarkRange('link').setLink({ href }).run()
  }
}

function removeLink() {
  editor.value?.chain().focus().extendMarkRange('link').unsetLink().run()
}

// -- Email boxes and buttons (email mode) ------------------------------------

const emailMenu = ref<'box' | 'button' | 'size' | 'gap' | null>(null)
const emailMenuOnRight = ref(false)

/** The look of the box or button the cursor is in, if it's one of the offered looks. */
const boxLook = computed(() => {
  void updateTick.value
  if (!editor.value?.isActive('emailBox')) return null
  return lookOf(BOX_LOOKS, editor.value.getAttributes('emailBox').style ?? '')?.id ?? null
})

const buttonLook = computed(() => {
  void updateTick.value
  if (!editor.value?.isActive('emailButton')) return null
  return lookOf(BUTTON_LOOKS, editor.value.getAttributes('emailButton').style ?? '')?.id ?? null
})

// Where the button the cursor is in sits on its line.
const BUTTON_PLACES = [
  { align: 'left', label: 'Left' },
  { align: 'center', label: 'Centre' },
] as const
const buttonAlign = computed(() => {
  void updateTick.value
  if (!editor.value?.isActive('emailButton')) return null
  return editor.value.getAttributes('emailButton').align === 'center' ? 'center' : 'left'
})

function alignButton(align: 'left' | 'center') {
  emailMenu.value = null
  editor.value?.chain().focus().setEmailButton({ align }).run()
}

/** The colour and size on the selected text, if it has its own. */
const colourAt = computed(() => {
  void updateTick.value
  return editor.value ? textStyleAt(editor.value.state, 'color') : { own: null, shown: null }
})

const sizeAt = computed(() => {
  void updateTick.value
  return editor.value ? textStyleAt(editor.value.state, 'font-size') : { own: null, shown: null }
})

// The size set on the text itself (the tool can take it off), and the one the
// text shows, which may come from its paragraph or heading. The shown colour
// is used by the color picker below.
const shownColour = computed(() => colourAt.value.shown)
const textSize = computed(() => sizeAt.value.own)
const shownSize = computed(() => sizeAt.value.shown)

const sizeNote = computed(() =>
  TEXT_SIZES.some((size) => size.value === shownSize.value) ? null : shownSize.value ? `Now: ${shownSize.value}` : 'Now: default'
)

/** Resize the selected text, or (null) take its size off. */
function chooseTextSize(size: string | null) {
  emailMenu.value = null
  editor.value?.chain().focus().setTextSize(size).run()
}

/** The gap below the selected paragraph, e.g. "24px", if it's set. */
const gapBelow = computed(() => {
  void updateTick.value
  return editor.value ? gapBelowSelection(editor.value.state) : null
})

/** Whether the cursor is somewhere a gap can be set: text, a box or a button. */
const canSetGap = computed(() => {
  void updateTick.value
  return !!editor.value && hasGapTarget(editor.value.state)
})

/** The gap now, when it isn't one of the offered gaps: "Now: 16px", or
 *  "Now: default" when none is set (the email app's usual space). */
const gapNote = computed(() => {
  if (!canSetGap.value) return 'Click in text, a box or a button first'
  if (TEXT_GAPS.some((gap) => gap.value === gapBelow.value)) return null
  return gapBelow.value ? `Now: ${gapBelow.value}` : 'Now: default'
})

/** Set the gap below the selected paragraphs and headings. */
function chooseGap(gap: string) {
  emailMenu.value = null
  editor.value?.chain().focus().setGapBelow(gap).run()
}

function toggleEmailMenu(menu: 'box' | 'button' | 'size' | 'gap', event: MouseEvent) {
  if (emailMenu.value === menu) {
    emailMenu.value = null
    return
  }
  // Open towards the side with room, so the editor's edge doesn't cut the menu off.
  const target = event.currentTarget as HTMLElement
  const button = target.getBoundingClientRect()
  const toolbar = target.closest('.rich-editor-toolbar')?.getBoundingClientRect()
  emailMenuOnRight.value = !!toolbar && button.left + button.width / 2 > toolbar.left + toolbar.width / 2
  showHeadingDropdown.value = false
  showFontDropdown.value = false
  showColorDropdown.value = false
  emailMenu.value = menu
}

/** Put the selected lines in a box of this look, restyle their box, or (null) unbox them. */
function chooseBoxLook(style: string | null) {
  emailMenu.value = null
  const chain = editor.value?.chain().focus()
  if (!chain) return
  if (style === null) chain.unsetEmailBox().run()
  else chain.setEmailBox(style).run()
}

/** Restyle the button the cursor is in, or ask for a link to make the current line a button. */
function chooseButtonLook(style: string) {
  emailMenu.value = null
  if (!editor.value) return
  if (editor.value.isActive('emailButton')) {
    editor.value.chain().focus().setEmailButton({ style }).run()
    return
  }
  linkDialog.value = { open: true, kind: 'button', adding: true, link: '', style }
}

function changeButtonLink() {
  emailMenu.value = null
  if (!editor.value) return
  const link = (editor.value.getAttributes('emailButton').href as string) || ''
  linkDialog.value = { open: true, kind: 'button', adding: false, link, style: '' }
}

function removeButton() {
  emailMenu.value = null
  editor.value?.chain().focus().setParagraph().run()
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

function formatFileSize(bytes?: number | null): string {
  if (!bytes || bytes <= 0) return '-'
  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let idx = 0
  while (size >= 1024 && idx < units.length - 1) {
    size /= 1024
    idx++
  }
  return `${size.toFixed(size >= 10 || idx === 0 ? 0 : 1)} ${units[idx]}`
}

async function uploadAndInsertAttachments(
  files: File[],
  range: { from: number; to: number } | null,
  acknowledgedOversized: boolean
) {
  uploadingAttachment.value = true
  attachmentError.value = null
  try {
    for (const [index, file] of files.entries()) {
      const resource = await uploadLinkedResourceAttachment(file, acknowledgedOversized)
      insertAttachmentLink(
        resource.downloadUrl || resource.accessUrl,
        index === 0 ? range : null
      )
    }
    pendingAttachmentFiles.value = []
    pendingAttachmentRange.value = null
  } catch (err: unknown) {
    console.error('Attachment upload failed:', err)
    attachmentError.value =
      err instanceof Error ? err.message : 'Attachment upload failed. Please try again.'
    if (acknowledgedOversized && pendingAttachmentFiles.value.length > 0) {
      acknowledgedOversizedAttachment.value = false
      emit('update:needsOversizeAck', true)
    }
  } finally {
    attachmentRange.value = null
    uploadingAttachment.value = false
  }
}

async function handleAttachmentFiles(files: File[]) {
  if (!files.length) return
  const initialRange = attachmentRange.value
  attachmentError.value = null

  const largeFile = files.find((f) => f.size > LARGE_FILE_BYTES) ?? null
  if (largeFile) {
    pendingAttachmentFiles.value = files
    pendingAttachmentRange.value = initialRange
    oversizedAttachmentFile.value = largeFile
    acknowledgedOversizedAttachment.value = false
    attachmentRange.value = null
    emit('update:needsOversizeAck', true)
    return
  }

  oversizedAttachmentFile.value = null
  pendingAttachmentFiles.value = []
  pendingAttachmentRange.value = null
  acknowledgedOversizedAttachment.value = false
  emit('update:needsOversizeAck', false)
  await uploadAndInsertAttachments(files, initialRange, false)
}

async function onOversizeAckChange() {
  if (acknowledgedOversizedAttachment.value && pendingAttachmentFiles.value.length > 0) {
    emit('update:needsOversizeAck', false)
    const filesToUpload = [...pendingAttachmentFiles.value]
    const rangeToUse = pendingAttachmentRange.value
    await uploadAndInsertAttachments(filesToUpload, rangeToUse, true)
  } else if (!acknowledgedOversizedAttachment.value && pendingAttachmentFiles.value.length > 0) {
    emit('update:needsOversizeAck', true)
  }
}

function toggleRawMode() {
  if (!editor.value) return
  if (rawMode.value) {
    // In emails the visual view can't hold everything HTML can: say what goes first.
    const losses = props.emailMode ? visualLosses(rawHtml.value) : []
    if (losses.length) {
      visualSwitch.value = { open: true, losses }
      return
    }
    showVisual()
  } else {
    rawMode.value = true
    // Exactly as given, unless the visual view has changed it since.
    if (visualEdited.value) {
      rawHtml.value = formatHtml(editor.value.getHTML())
      emit('update:modelValue', rawHtml.value)
      emit('change', rawHtml.value)
    }
  }
}

/** Back to the visual view, rebuilt from the HTML (which still holds as typed). */
function showVisual() {
  if (!editor.value) return
  rawMode.value = false
  // Not an edit: the HTML as typed is what's kept until the visual view changes it.
  editor.value.commands.setContent(rawHtml.value || '', { emitUpdate: false })
  visualEdited.value = false
  emit('update:modelValue', rawHtml.value)
  emit('change', rawHtml.value)
}

/** Switched despite the warning: the content is now what the visual view holds. */
function showVisualAnyway() {
  visualSwitch.value = { open: false, losses: [] }
  showVisual()
  if (!editor.value) return
  const rebuilt = editor.value.getHTML()
  rawHtml.value = rebuilt
  visualEdited.value = true
  emit('update:modelValue', rebuilt)
  emit('change', rebuilt)
}

function handleRawInput(e: Event) {
  const target = e.target as HTMLTextAreaElement
  rawHtml.value = target.value
  emit('update:modelValue', target.value)
  emit('change', target.value)
}

/**
 * Insert a merge tag (or any text) at the cursor. Exposed so the email page's
 * merge-tag palette can drop `{{ first_name }}` exactly where the admin is
 * typing instead of appending it to the end of the body.
 */
function insertText(text: string) {
  if (props.readOnly || !text) return
  if (rawMode.value) {
    const next = rawHtml.value ? `${rawHtml.value} ${text}` : text
    rawHtml.value = next
    emit('update:modelValue', next)
    emit('change', next)
    return
  }
  editor.value?.chain().focus().insertContent(text).run()
}

defineExpose({ insertText })
</script>

<template>
  <div
    class="rich-editor-wrapper"
    :class="{ 'rich-editor-wrapper--compact': compact }"
    @focusin="emit('focus')"
  >
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
              @click="showHeadingDropdown = !showHeadingDropdown; showFontDropdown = false; showColorDropdown = false; emailMenu = null"
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

          <!-- Font Family Dropdown -->
          <div class="heading-dropdown-container font-dropdown-container">
            <button
              type="button"
              class="toolbar-btn heading-btn font-btn"
              :title="`Current font: ${currentFontLabel}`"
              @click="showFontDropdown = !showFontDropdown; showHeadingDropdown = false; showColorDropdown = false; emailMenu = null"
            >
              <span :style="{ fontFamily: currentFontFamilyStyle }">{{ currentFontLabel }}</span>
              <i class="fas fa-chevron-down heading-chevron"></i>
            </button>
            <div v-if="showFontDropdown" class="heading-dropdown-menu font-dropdown-menu">
              <button
                type="button"
                class="dropdown-item font-item-arial"
                :class="{ active: currentFontLabel === 'Arial' }"
                @click="selectFont('Arial')"
              >
                Arial
              </button>
              <button
                type="button"
                class="dropdown-item font-item-times"
                :class="{ active: currentFontLabel === 'Times New Roman' }"
                @click="selectFont('Times New Roman')"
              >
                Times New Roman
              </button>
            </div>
          </div>

          <!-- Text colour, size and gap, kept on save, in every editor -->
          <div class="toolbar-sep"></div>

          <!-- Text Color Dropdown -->
          <div class="heading-dropdown-container color-dropdown-container">
            <button
              type="button"
              class="toolbar-btn text-icon-btn color-picker-btn"
              :class="{ 'color-picker-btn--open': showColorDropdown || (emailMode ? !!colourAt.own : isActive('textColor')) }"
              :title="`Text color (${currentTextColor})`"
              data-test="text-colour"
              @click="toggleColorDropdown($event)"
            >
              <span class="color-picker-icon">
                <span class="color-picker-glyph">A</span>
                <span
                  class="color-picker-bar"
                  :class="{ 'color-picker-bar--light': currentTextColor === '#FFFFFF' }"
                  :style="{ backgroundColor: currentTextColor }"
                ></span>
              </span>
              <i class="fas fa-chevron-down heading-chevron"></i>
            </button>
            <div
              v-if="showColorDropdown"
              class="color-dropdown-menu"
              :class="{ 'color-dropdown-menu--right': colorMenuOnRight }"
            >
              <div
                v-for="section in COLOR_SECTIONS"
                :key="section.title"
                class="color-section"
              >
                <div class="color-section-title">{{ section.title }}</div>
                <div class="color-section-grid">
                  <button
                    v-for="option in section.colors"
                    :key="option.hex"
                    type="button"
                    class="color-option-card"
                    :class="{ active: currentTextColor === option.hex }"
                    @click="selectColor(option.hex)"
                  >
                    <span
                      class="color-option-swatch"
                      :class="{ 'color-option-swatch--white': option.hex === '#FFFFFF' }"
                      :style="{ backgroundColor: option.hex }"
                    ></span>
                    <span class="color-option-info">
                      <span class="color-option-name">{{ option.name }}</span>
                      <span class="color-option-hex">{{ option.hex }}</span>
                    </span>
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div class="heading-dropdown-container">
            <button
              type="button"
              class="toolbar-btn text-icon-btn"
              :class="{ active: !!textSize }"
              title="Resize the selected text"
              data-test="text-size"
              @mousedown.prevent="toggleEmailMenu('size', $event)"
            >
              <i class="fas fa-text-height"></i>
              <i class="fas fa-chevron-down heading-chevron"></i>
            </button>
            <div
              v-if="emailMenu === 'size'"
              class="heading-dropdown-menu email-look-menu"
              :class="{ 'email-look-menu--right': emailMenuOnRight }"
            >
              <template v-if="sizeNote">
                <div class="dropdown-item text-now active" data-test="size-now">{{ sizeNote }}</div>
                <div class="email-look-sep"></div>
              </template>
              <button
                v-for="size in TEXT_SIZES"
                :key="size.value"
                type="button"
                class="dropdown-item"
                :class="{ active: shownSize === size.value }"
                :style="{ fontSize: size.value }"
                @mousedown.prevent="chooseTextSize(size.value)"
              >
                {{ size.label }}
              </button>
              <template v-if="textSize">
                <div class="email-look-sep"></div>
                <button type="button" class="dropdown-item" @mousedown.prevent="chooseTextSize(null)">
                  Normal size
                </button>
              </template>
            </div>
          </div>
          <div class="heading-dropdown-container">
            <button
              type="button"
              class="toolbar-btn text-icon-btn"
              title="Gap below the selected paragraphs, box or button"
              data-test="text-gap"
              @mousedown.prevent="toggleEmailMenu('gap', $event)"
            >
              <i class="fas fa-arrows-up-down"></i>
              <i class="fas fa-chevron-down heading-chevron"></i>
            </button>
            <div
              v-if="emailMenu === 'gap'"
              class="heading-dropdown-menu email-look-menu"
              :class="{ 'email-look-menu--right': emailMenuOnRight }"
            >
              <template v-if="gapNote">
                <div
                  class="dropdown-item gap-now"
                  :class="{ active: canSetGap }"
                  data-test="gap-now"
                  :title="gapBelow ? undefined : 'No gap is set here: the email app puts its usual space after a paragraph'"
                >
                  {{ gapNote }}
                </div>
                <div class="email-look-sep"></div>
              </template>
              <button
                v-for="gap in TEXT_GAPS"
                :key="gap.value"
                type="button"
                class="dropdown-item"
                :class="{ active: gapBelow === gap.value }"
                :disabled="!canSetGap"
                @mousedown.prevent="chooseGap(gap.value)"
              >
                {{ gap.label }} ({{ gap.value }})
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
            v-if="allowManualLinks"
            type="button"
            class="toolbar-btn icon-btn"
            :class="{ active: isActive('link') }"
            title="Insert / edit link"
            @mousedown.prevent="editLink"
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
            title="Horizontal rule"
            @mousedown.prevent="editor?.chain().focus().setHorizontalRule().run()"
          >
            <i class="fas fa-minus"></i>
          </button>

          <!-- Box and Button, kept on save, in every editor -->
          <div class="heading-dropdown-container">
            <button
              type="button"
              class="toolbar-btn text-icon-btn"
              :class="{ active: isActive('emailBox') }"
              title="Put the selected lines in a box, change the box, or take them out"
              @mousedown.prevent="toggleEmailMenu('box', $event)"
            >
              <i class="far fa-square"></i>
              <span>Box</span>
              <i class="fas fa-chevron-down heading-chevron"></i>
            </button>
            <div
              v-if="emailMenu === 'box'"
              class="heading-dropdown-menu email-look-menu"
              :class="{ 'email-look-menu--right': emailMenuOnRight }"
            >
              <button
                v-for="look in BOX_LOOKS"
                :key="look.id"
                type="button"
                class="dropdown-item email-look-item"
                :class="{ active: boxLook === look.id }"
                @mousedown.prevent="chooseBoxLook(look.style)"
              >
                <span class="email-look-swatch" :style="swatchOf(look)"></span>
                {{ look.label }}
              </button>
              <template v-if="isActive('emailBox')">
                <div class="email-look-sep"></div>
                <button type="button" class="dropdown-item" @mousedown.prevent="chooseBoxLook(null)">
                  No box
                </button>
              </template>
            </div>
          </div>
          <div class="heading-dropdown-container">
            <button
              type="button"
              class="toolbar-btn text-icon-btn"
              :class="{ active: isActive('emailButton') }"
              title="Turn this line into a button, or change the button"
              @mousedown.prevent="toggleEmailMenu('button', $event)"
            >
              <i class="fas fa-hand-pointer"></i>
              <span>Button</span>
              <i class="fas fa-chevron-down heading-chevron"></i>
            </button>
            <div
              v-if="emailMenu === 'button'"
              class="heading-dropdown-menu email-look-menu"
              :class="{ 'email-look-menu--right': emailMenuOnRight }"
            >
              <button
                v-for="look in BUTTON_LOOKS"
                :key="look.id"
                type="button"
                class="dropdown-item email-look-item"
                :class="{ active: buttonLook === look.id }"
                @mousedown.prevent="chooseButtonLook(look.style)"
              >
                <span class="email-look-swatch" :style="swatchOf(look)"></span>
                {{ look.label }}
              </button>
              <template v-if="isActive('emailButton')">
                <div class="email-look-sep"></div>
                <!-- Where the button sits on its line: left, or centred. -->
                <button
                  v-for="place in BUTTON_PLACES"
                  :key="place.align"
                  type="button"
                  class="dropdown-item"
                  :class="{ active: buttonAlign === place.align }"
                  @mousedown.prevent="alignButton(place.align)"
                >
                  {{ place.label }}
                </button>
                <div class="email-look-sep"></div>
                <button type="button" class="dropdown-item" @mousedown.prevent="changeButtonLink">
                  Change link…
                </button>
                <button type="button" class="dropdown-item" @mousedown.prevent="removeButton">
                  No button
                </button>
              </template>
            </div>
          </div>

          <div class="toolbar-sep"></div>

          <!-- Insert Actions (images and files hidden in email mode: nh3 strips them) -->
          <template v-if="!emailMode">
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
              v-if="allowAttachments"
              type="button"
              class="toolbar-btn text-icon-btn"
              title="Attach file to selected text"
              :disabled="uploadingAttachment"
              @mousedown.prevent="openAttachmentPicker"
            >
              <i class="fas fa-paperclip"></i>
              <span>{{ uploadingAttachment ? 'Uploading…' : 'File' }}</span>
            </button>
          </template>
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

        <!-- Lines on or off for the whole table (email mode) -->
        <template v-if="emailMode">
          <div class="toolbar-sep"></div>
          <button
            type="button"
            class="table-action-btn"
            :class="{ active: tableHasLines }"
            :aria-pressed="tableHasLines"
            title="Draw or take away this table's lines"
            data-test="table-lines"
            @mousedown.prevent="editor?.chain().focus().toggleTableLines().run()"
          >
            <i class="fas fa-border-all"></i>
            <span>{{ tableHasLines ? 'Lines on' : 'Lines off' }}</span>
          </button>
        </template>

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
          :readonly="readOnly"
          class="raw-html-textarea"
          placeholder="<p>HTML content…</p>"
          @input="handleRawInput"
        ></textarea>
      </div>
      <div v-else class="rich-editor-content-area" @mousedown="emailMenu = null">
        <EditorContent :editor="editor" />
      </div>

      <!-- Switching to the visual view would drop part of the HTML (email mode) -->
      <ConfirmDialog
        v-model="visualSwitch.open"
        title="Switch to the visual view?"
        message="The visual view can't keep everything in this HTML. Switching rebuilds it and drops:"
        confirm-label="Switch anyway"
        cancel-label="Stay in HTML"
        variant="warning"
        @confirm="showVisualAnyway"
      >
        <ul class="visual-losses" data-test="visual-losses">
          <li v-for="loss in visualSwitch.losses" :key="loss">{{ loss }}</li>
        </ul>
      </ConfirmDialog>
    </div>

    <!-- Large files are allowed once the admin confirms -->
    <div v-if="oversizedAttachmentFile" class="rich-editor-oversize" role="alert">
      <p class="rich-editor-oversize__text">
        <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
        This file is {{ formatFileSize(oversizedAttachmentFile.size) }}, over the 25 MB guideline. Large files
        take longer to upload and open.
      </p>
      <label class="rich-editor-oversize__checkbox-label">
        <input
          id="rich-editor-oversize-ack"
          v-model="acknowledgedOversizedAttachment"
          type="checkbox"
          :disabled="uploadingAttachment"
          @change="onOversizeAckChange"
        />
        <span>I understand this file is large</span>
      </label>
    </div>

    <LinkDialog
      v-model="linkDialog.open"
      :kind="linkDialog.kind"
      :adding="linkDialog.adding"
      :initial-link="linkDialog.link"
      :placeholders="linkPlaceholders"
      :allow-relative="!emailMode"
      @confirm="onLinkChosen"
      @remove="removeLink"
      @cancel="editor?.commands.focus()"
    />

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
      v-if="allowAttachments"
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

.rich-editor-oversize {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-top: 0.25rem;
  padding: 0.65rem 0.85rem;
  border-radius: 6px;
  background-color: #fffbeb;
  border: 1px solid #fcd34d;
}

.rich-editor-oversize__text {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  margin: 0;
  font-size: 0.85rem;
  color: #92400e;
}

.rich-editor-oversize__checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: var(--charcoal, #1f2937);
  cursor: pointer;
}

.rich-editor-oversize__checkbox-label input {
  accent-color: var(--dark-green, #017151);
  width: 16px;
  height: 16px;
  cursor: pointer;
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
  overflow: visible;
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
  border-radius: 0.5rem 0.5rem 0 0;
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
  border: 1px solid transparent;
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
  border-color: #017151;
  background-color: #f0fdf4;
  color: #017151;
}

.toolbar-btn.active:hover {
  background-color: #dcfce7;
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
  background-color: #e8f5f1;
  color: #017151;
  font-weight: 600;
}

.font-btn {
  min-width: 9.5rem;
}

.font-dropdown-menu {
  min-width: 9.5rem;
}

.font-item-arial {
  font-family: Arial, sans-serif;
}

.font-item-times {
  font-family: 'Times New Roman', Times, serif;
}

.color-picker-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid transparent;
  border-radius: 0.3125rem;
}

.color-picker-icon {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.1rem;
}

.color-picker-btn--open {
  border-color: #017151;
  background-color: #f0fdf4;
}

.color-picker-glyph {
  font-size: 0.8125rem;
  font-weight: 700;
  line-height: 1;
  color: #1f2937;
}

.color-picker-bar {
  width: 0.875rem;
  height: 0.1875rem;
  border-radius: 9999px;
  flex-shrink: 0;
}

.color-picker-bar--light {
  box-shadow: inset 0 0 0 1px #94a3b8;
}

.color-dropdown-menu {
  position: absolute;
  top: 100%;
  left: 0;
  z-index: 50;
  margin-top: 0.375rem;
  width: 17.5rem;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 0.75rem;
  box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.12), 0 4px 10px -4px rgba(15, 23, 42, 0.07);
  padding: 0.875rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.color-dropdown-menu--right {
  left: auto;
  right: 0;
}

.color-section {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.color-section-title {
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.03em;
  color: #64748b;
  text-transform: uppercase;
}

.color-section-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.45rem;
}

.color-option-card {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.375rem 0.5rem;
  background: #ffffff;
  border: 1px solid #cbd5e1;
  border-radius: 0.375rem;
  cursor: pointer;
  text-align: left;
  transition: all 0.15s ease;
}

.color-option-card:hover {
  border-color: #94a3b8;
  background-color: #f8fafc;
}

.color-option-card.active {
  border-color: #017151;
  background-color: #f0fdf4;
  box-shadow: 0 0 0 1px #017151;
}

.color-option-swatch {
  width: 0.9375rem;
  height: 0.9375rem;
  border-radius: 9999px;
  flex-shrink: 0;
  border: 1px solid rgba(15, 23, 42, 0.15);
}

.color-option-swatch--white {
  border: 1px solid #94a3b8;
}

.color-option-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
  line-height: 1.15;
}

.color-option-name {
  font-size: 0.6875rem;
  font-weight: 600;
  color: #1e293b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.color-option-hex {
  font-size: 0.5625rem;
  font-weight: 500;
  color: #64748b;
  letter-spacing: 0.01em;
}

/* What switching to the visual view would drop, in its warning. */
.visual-losses {
  margin: 0.5rem 0 0 1.25rem;
  padding: 0;
}

/* The gap now, when it isn't one on offer: shown, not picked. */
.dropdown-item.gap-now,
.dropdown-item.text-now {
  cursor: default;
}

.email-look-menu {
  min-width: 10.5rem;
}

.email-look-menu--right {
  left: auto;
  right: 0;
}

.email-look-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.email-look-swatch {
  flex: none;
  width: 1.25rem;
  height: 0.875rem;
  border-radius: 0.1875rem;
}

.email-look-sep {
  height: 1px;
  margin: 0.25rem 0.125rem;
  background-color: #e5e7eb;
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
  border: 1px solid transparent;
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

.table-action-btn.active {
  border-color: #017151;
  background-color: #f0fdf4;
  color: #017151;
  font-weight: 600;
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

.rich-editor-wrapper--compact .rich-editor-content-area {
  min-height: 12rem;
  padding: 0.75rem 1rem;
}

.rich-editor-wrapper--compact .rich-editor-raw-area .raw-html-textarea {
  min-height: 12rem;
  padding: 0.75rem 1rem;
}
</style>

<style>
/* TipTap ProseMirror content styling */
.rich-editor-content-area .tiptap.ProseMirror {
  outline: none;
  min-height: 18rem;
  font-family: Arial, sans-serif;
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

/* Email boxes and buttons carry their own inline styles; match the email's spacing. */
.rich-editor-content-area .tiptap.ProseMirror .email-box p {
  margin: 0 0 10px 0;
}

.rich-editor-content-area .tiptap.ProseMirror .email-box p:last-child {
  margin-bottom: 0;
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

.rich-editor-wrapper--compact .rich-editor-content-area .tiptap.ProseMirror {
  min-height: 10rem;
}
</style>
