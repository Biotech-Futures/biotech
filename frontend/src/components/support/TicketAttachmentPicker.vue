<template>
  <div
    class="attach"
    :class="{ 'attach--over': isOver }"
    @dragover.prevent="isOver = true"
    @dragenter.prevent="isOver = true"
    @dragleave="isOver = false"
    @drop.prevent="onDrop"
  >
    <label class="attach__button">
      <input
        ref="input"
        type="file"
        multiple
        :accept="ACCEPT"
        class="attach__input"
        @change="onPick"
      />
      <TicketIcon name="paperclip" :size="14" />
      <span>Attach files</span>
    </label>
    <span class="attach__hint">Drag and drop files here or click to attach. {{ ATTACHMENT_HINT }}</span>

    <ul v-if="modelValue.length" class="attach__list">
      <li v-for="(file, index) in modelValue" :key="`${file.name}-${index}`" class="attach__item">
        <span class="attach__kind"><TicketIcon :name="kindIcon(file)" /></span>
        <span class="attach__name">{{ file.name }}</span>
        <span class="attach__size">{{ readableSize(file.size) }}</span>
        <button type="button" class="attach__remove" :aria-label="`Remove ${file.name}`" @click="remove(index)">
          <TicketIcon name="x" />
        </button>
      </li>
    </ul>

    <p v-if="error" class="attach__error"><TicketIcon name="alert" /><span>{{ error }}</span></p>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import TicketIcon from '@/components/support/TicketIcon.vue'
import { ATTACHMENT_HINT, MAX_ATTACHMENTS, MAX_ATTACHMENT_BYTES } from '@/utils/supportAPI'

const ACCEPT = '.pdf,.png,.jpg,.jpeg,.docx'

// The same list the input advertises, as a set the code can test against.
// `accept` is a filter for the operating system's file dialog and nothing
// else: it has no effect on a file dropped onto the page, so without this the
// drop zone would hand a .exe to the uploader and let the server be the first
// thing to say no.
const ALLOWED_EXTENSIONS = ACCEPT.split(',')

const props = defineProps<{ modelValue: File[] }>()
const emit = defineEmits<{ 'update:modelValue': [File[]] }>()

const input = ref<HTMLInputElement | null>(null)
const error = ref('')
const isOver = ref(false)

function hasAllowedExtension(file: File): boolean {
  const name = file.name.toLowerCase()
  return ALLOWED_EXTENSIONS.some((extension) => name.endsWith(extension))
}

// A picture for the pictures, a page for the documents. Only the look
// depends on it; every name the input accepts gets one or the other.
function kindIcon(file: File): 'image' | 'file' {
  return /\.(png|jpe?g)$/i.test(file.name) ? 'image' : 'file'
}

function readableSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// Checked here as well as on the server. The server is the one that decides,
// but telling someone their 40 MB file is too big before they wait for it to
// upload is the difference between a hint and a rejection.
function take(picked: File[]) {
  if (!picked.length) return
  error.value = ''

  // Wrong type first: a file rejected for its type is not then also reported
  // as too big, which would be two complaints about one mistake.
  const wrongType = picked.find((file) => !hasAllowedExtension(file))
  if (wrongType) {
    error.value = `${wrongType.name} is not a PDF, PNG, JPG or DOCX.`
  }
  const rightType = picked.filter(hasAllowedExtension)

  const tooBig = rightType.find((file) => file.size > MAX_ATTACHMENT_BYTES)
  if (tooBig) {
    error.value = `${tooBig.name} is larger than 10 MB.`
  }

  const accepted = rightType.filter((file) => file.size <= MAX_ATTACHMENT_BYTES)
  const combined = [...props.modelValue, ...accepted]
  if (combined.length > MAX_ATTACHMENTS) {
    error.value = `You can attach up to ${MAX_ATTACHMENTS} files to one message.`
  }

  emit('update:modelValue', combined.slice(0, MAX_ATTACHMENTS))
}

function onPick(event: Event) {
  take(Array.from((event.target as HTMLInputElement).files || []))
  // Clearing it is what lets the same file be picked twice in a row: without
  // this the input holds the old value and fires no change event.
  if (input.value) input.value.value = ''
}

function onDrop(event: DragEvent) {
  isOver.value = false
  take(Array.from(event.dataTransfer?.files || []))
}

function remove(index: number) {
  const next = [...props.modelValue]
  next.splice(index, 1)
  emit('update:modelValue', next)
  error.value = ''
}
</script>

<style scoped>
/* The first redesign round (October 2026) lines the picker up with the
   fields above it and gives each chosen file a card of its own. Colours are
   the component's own; it sits in the new-ticket form and in the reply box,
   and both paint it on a card (white in light, #1d2826 in dark).

   Measured (WCAG AA: 4.5:1 for text, 3:1 for a control's edge or an icon):
     light  muted #5a6268 on the card 6.21:1, on the #f8f9fa file row 5.89:1
            button edge #84938f on the card 3.21:1
            error #a71d2a on #fdf0f0 6.63:1   file icon #017151 on #fcede2 5.27:1
     dark   muted #a3b3ae on the #0f1715 file row 8.34:1, on the card 6.95:1
            button edge #70827d on the card 3.74:1
            error #f87171 on #3a1d20 5.52:1   file icon #6dbfb1 on #143b32 5.72:1
   The dark error and file tile are the colours this feature already uses for
   Overdue and the help topics; the designer drew neither in dark. */
.attach {
  --attach-muted: #5a6268;
  --attach-edge: #84938f;
  --attach-rule: #e6eae8;
  --attach-hover: var(--dark-green);
  --attach-tile: #fcede2;
  --attach-tile-ink: #017151;
  --attach-danger: #a71d2a;
  --attach-danger-ground: #fdf0f0;

  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  /* The padding is room for the drop highlight; the margin takes the same
     space back, so at rest the button lines up with the fields above. */
  padding: 0.6rem;
  margin: calc(-0.6rem - 1px);
  border: 1px dashed transparent;
  border-radius: 8px;
  transition: border-color 0.15s ease, background 0.15s ease;
}

:root[data-theme='dark'] .attach {
  --attach-muted: #a3b3ae;
  --attach-edge: #70827d;
  --attach-rule: #2b3936;
  --attach-hover: #6dbfb1;
  --attach-tile: #143b32;
  --attach-tile-ink: #6dbfb1;
  --attach-danger: #f87171;
  --attach-danger-ground: #3a1d20;
}

/* Only while something is being dragged over it. A permanent dashed box
   around the button would read as a disabled field. */
.attach--over {
  border-color: var(--dark-green);
  background: var(--bg-light);
}

.attach__button {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  min-height: 2.25rem;
  padding: 0 1rem 0 0.95rem;
  border: 1px solid var(--attach-edge);
  border-radius: 8px;
  background: var(--surface-elevated);
  color: var(--charcoal);
  font-size: 0.88rem;
  cursor: pointer;
}

.attach__button:hover {
  border-color: var(--attach-hover);
  color: var(--attach-hover);
}

.attach__input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.attach__hint {
  color: var(--attach-muted);
  font-size: 0.8rem;
}

.attach__list {
  flex-basis: 100%;
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.attach__item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.375rem 0.5rem;
  border: 1px solid var(--attach-rule);
  border-radius: 8px;
  background: var(--bg-light);
  font-size: 0.85rem;
}

.attach__kind {
  display: flex;
  flex: none;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border-radius: 6px;
  background: var(--attach-tile);
  color: var(--attach-tile-ink);
}

.attach__name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
}

.attach__size {
  color: var(--attach-muted);
  font-size: 0.8rem;
}

/* 24 by 24, the smallest target WCAG 2.2 AA allows, with the cross drawn in
   the middle of it. */
.attach__remove {
  display: flex;
  flex: none;
  align-items: center;
  justify-content: center;
  width: 1.5rem;
  height: 1.5rem;
  margin-left: 0.25rem;
  padding: 0;
  border: none;
  border-radius: 6px;
  background: none;
  color: var(--attach-muted);
  cursor: pointer;
}

.attach__remove:hover {
  color: var(--attach-danger);
}

.attach__error {
  flex-basis: 100%;
  display: flex;
  align-items: center;
  gap: 0.625rem;
  margin: 0;
  padding: 0.55rem 0.8rem;
  border-left: 4px solid var(--attach-danger);
  border-radius: 4px;
  background: var(--attach-danger-ground);
  color: var(--attach-danger);
  font-size: 0.85rem;
  font-weight: 600;
  line-height: 1.5;
}
</style>
