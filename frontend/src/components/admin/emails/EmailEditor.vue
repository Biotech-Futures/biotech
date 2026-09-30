<template>
  <section class="email-editor" aria-label="Email editor">
    <header class="email-editor__header">
      <div class="email-editor__title-block">
        <h2 class="email-editor__title">
          {{ emailTemplate.name }}
          <i
            v-if="emailTemplate.locked"
            class="fas fa-lock email-editor__lock"
            title="This email is required and cannot be switched off"
            aria-hidden="true"
          ></i>
        </h2>
        <p class="email-editor__description">{{ emailTemplate.description }}</p>
        <p v-if="lastEditedLabel()" class="email-editor__last-edited">
          <i class="fas fa-user-pen" aria-hidden="true"></i>
          {{ lastEditedLabel() }}
        </p>
      </div>

      <label class="email-editor__switch">
        <input
          type="checkbox"
          class="sr-only"
          role="switch"
          :checked="emailTemplate.enabled"
          :disabled="emailTemplate.locked || busy"
          :aria-label="`Send ${emailTemplate.name}`"
          @change="onToggleEnabled(($event.target as HTMLInputElement).checked)"
        />
        <span class="email-editor__switch-track" aria-hidden="true">
          <span class="email-editor__switch-knob"></span>
        </span>
        <span class="email-editor__switch-label">
          {{ emailTemplate.enabled ? 'Sending' : 'Paused' }}
        </span>
      </label>
    </header>

    <p v-if="emailTemplate.locked" class="email-editor__note">
      <i class="fas fa-shield-halved" aria-hidden="true"></i>
      {{ lockReason() }}
    </p>

    <p
      v-if="!emailTemplate.usingSavedContent"
      class="email-editor__note email-editor__note--muted"
    >
      <i class="fas fa-wand-magic-sparkles" aria-hidden="true"></i>
      These are the current built-in contents. Save to switch to your custom wording.
      Saving your own wording replaces the built-in design: boxes and buttons are kept, but
      other styling, such as coloured or smaller text, becomes plain.
    </p>

    <!-- Tags go into whichever of Subject or Body was used last. -->
    <div class="email-editor__field">
      <span class="email-editor__label">Placeholders</span>
      <MergeTagPalette :tags="emailTemplate.mergeTags" @insert="onInsertTag" />
    </div>

    <div class="email-editor__field">
      <label class="email-editor__label" for="template-subject">Subject</label>
      <!-- Not a login field: an id with "email" in it, and no autocomplete
           hint, made password managers (Bitwarden) offer to fill it. -->
      <input
        id="template-subject"
        ref="subjectInput"
        type="text"
        autocomplete="off"
        data-bwignore
        data-1p-ignore
        data-lpignore="true"
        class="email-editor__subject"
        :value="subject"
        :placeholder="emailTemplate.defaultSubject"
        :disabled="busy"
        maxlength="255"
        @focus="activeField = 'subject'"
        @input="emit('update:subject', ($event.target as HTMLInputElement).value)"
      />
    </div>

    <div class="email-editor__field">
      <label class="email-editor__label">Body</label>
      <div class="email-editor__body" @focusin="activeField = 'body'">
        <RichEditor
          ref="bodyEditor"
          :model-value="body"
          email-mode
          compact
          :link-placeholders="linkPlaceholders"
          :read-only="busy"
          @update:model-value="emit('update:body', $event)"
          @focus="activeField = 'body'"
        />
      </div>
    </div>

    <footer class="email-editor__actions">
      <div class="email-editor__actions-primary">
        <button
          type="button"
          class="btn btn-primary"
          :disabled="!dirty || busy"
          @click="emit('save')"
        >
          <i v-if="saving" class="fas fa-spinner fa-spin" aria-hidden="true"></i>
          <i v-else class="fas fa-floppy-disk" aria-hidden="true"></i>
          <span>{{ saving ? 'Saving…' : 'Save changes' }}</span>
        </button>
        <button
          type="button"
          class="btn btn-outline"
          :disabled="!emailTemplate.usingSavedContent || busy"
          @click="emit('restore')"
        >
          <i v-if="restoring" class="fas fa-spinner fa-spin" aria-hidden="true"></i>
          <i v-else class="fas fa-rotate-left" aria-hidden="true"></i>
          <span>{{ restoring ? 'Restoring…' : 'Restore default' }}</span>
        </button>
      </div>

      <div class="email-editor__actions-secondary">
        <button type="button" class="btn btn-outline" :disabled="busy" @click="emit('test-send')">
          <i v-if="testing" class="fas fa-spinner fa-spin" aria-hidden="true"></i>
          <i v-else class="fas fa-paper-plane" aria-hidden="true"></i>
          <span>{{ testing ? 'Sending…' : 'Send test' }}</span>
        </button>
      </div>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, ref } from 'vue'
import MergeTagPalette from '@/components/admin/emails/MergeTagPalette.vue'
import { isLinkPlaceholder } from '@/components/admin/emailBlocks'
import { mergeTagToken, type SystemEmailMergeTag, type SystemEmailTemplate } from '@/utils/systemEmail'

const RichEditor = defineAsyncComponent(() => import('@/components/admin/RichEditor.vue'))

const props = defineProps<{
  emailTemplate: SystemEmailTemplate
  subject: string
  body: string
  dirty: boolean
  busy: boolean
  saving: boolean
  testing: boolean
  restoring: boolean
}>()

/** This email's placeholders that hold a link, offered in the link dialog. */
const linkPlaceholders = computed(() =>
  props.emailTemplate.mergeTags.filter((tag) => isLinkPlaceholder(tag.name)).map((tag) => mergeTagToken(tag.name))
)

const lockReason = () => {
  if (!props.emailTemplate.locked) return ''
  switch (props.emailTemplate.key) {
    case 'login_code':
      return 'Account sign-in would break if this email were paused, so it always sends.'
    case 'password_reset':
    case 'password_changed':
      return 'Account security depends on this email reaching users, so it always sends.'
    default:
      return 'This email is required by the platform, so it always sends.'
  }
}

const lastEditedLabel = () => {
  const { updatedBy, updatedAt } = props.emailTemplate
  if (!updatedBy || !updatedAt) return ''
  const when = new Date(updatedAt).toLocaleString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit'
  })
  return `Last edited by ${updatedBy} \u00b7 ${when}`
}

const emit = defineEmits<{
  (e: 'update:subject', value: string): void
  (e: 'update:body', value: string): void
  (e: 'toggle-enabled', enabled: boolean): void
  (e: 'save'): void
  (e: 'restore'): void
  (e: 'test-send'): void
}>()

type EditableField = 'subject' | 'body'

const activeField = ref<EditableField>('body')
const subjectInput = ref<HTMLInputElement | null>(null)
const bodyEditor = ref<{ insertText: (text: string) => void } | null>(null)

const onToggleEnabled = (enabled: boolean) => {
  if (props.emailTemplate.locked && !enabled) return
  emit('toggle-enabled', enabled)
}

const onInsertTag = (tag: SystemEmailMergeTag) => {
  const token = mergeTagToken(tag.name)
  if (activeField.value === 'subject') {
    insertIntoSubject(token)
  } else {
    bodyEditor.value?.insertText(token)
  }
}

/** Insert at the caret (or append) so tags land where the admin is typing. */
const insertIntoSubject = (token: string) => {
  const input = subjectInput.value
  if (!input) {
    emit('update:subject', `${props.subject}${token}`)
    return
  }
  const start = input.selectionStart ?? input.value.length
  const end = input.selectionEnd ?? start
  const next = `${input.value.slice(0, start)}${token}${input.value.slice(end)}`
  emit('update:subject', next)
  void nextTick(() => {
    input.focus()
    const caret = start + token.length
    input.setSelectionRange(caret, caret)
  })
}
</script>

<style scoped>
.email-editor {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  min-width: 0;
}

.email-editor__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.email-editor__title {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0 0 0.25rem;
  font-size: 1.0625rem;
  font-weight: 600;
  color: #111827;
}

.email-editor__lock {
  font-size: 0.75rem;
  color: #6b7280;
}

.email-editor__description {
  margin: 0;
  font-size: 0.8125rem;
  color: #6b7280;
}

.email-editor__switch {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
  cursor: pointer;
}

.email-editor__switch input:disabled + .email-editor__switch-track {
  opacity: 0.5;
  cursor: not-allowed;
}

.email-editor__switch-track {
  position: relative;
  display: inline-block;
  width: 2.5rem;
  height: 1.375rem;
  border-radius: 999px;
  background: #d1d5db;
  transition: background-color 0.15s ease;
}

.email-editor__switch input:checked + .email-editor__switch-track {
  background: var(--dark-green);
}

.email-editor__switch-knob {
  position: absolute;
  top: 0.1875rem;
  left: 0.1875rem;
  width: 1rem;
  height: 1rem;
  border-radius: 50%;
  background: #ffffff;
  transition: transform 0.15s ease;
}

.email-editor__switch input:checked + .email-editor__switch-track .email-editor__switch-knob {
  transform: translateX(1.125rem);
}

.email-editor__switch-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: #4b5563;
  min-width: 3.5rem;
}

.email-editor__last-edited {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  margin: 0.25rem 0 0;
  font-size: 0.75rem;
  color: #6b7280;
}

.email-editor__note {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0;
  padding: 0.5rem 0.75rem;
  border-radius: 0.375rem;
  background: var(--accent-green-soft);
  font-size: 0.75rem;
  color: var(--dark-green);
}

.email-editor__note--muted {
  background: #f9fafb;
  color: #6b7280;
}

.email-editor__field {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.email-editor__label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #6b7280;
}

.email-editor__subject {
  width: 100%;
  padding: 0.5rem 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  color: #111827;
}

.email-editor__subject:focus {
  outline: none;
  border-color: var(--dark-green);
  box-shadow: 0 0 0 3px rgba(1, 113, 81, 0.15);
}

.email-editor__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding-top: 0.5rem;
  border-top: 1px solid #e5e7eb;
}

.email-editor__actions-primary,
.email-editor__actions-secondary {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

/* Dark theme: the note, subject and body editor take the grey other pages
   give their boxes, with light text. */
:root[data-theme='dark'] .email-editor__title {
  color: var(--charcoal);
}

:root[data-theme='dark'] .email-editor__switch-label {
  color: var(--text-muted);
}

:root[data-theme='dark'] .email-editor__note--muted,
:root[data-theme='dark'] .email-editor__subject {
  background: var(--surface-elevated);
  color: var(--charcoal);
  border-color: var(--border-light);
}

:root[data-theme='dark'] .email-editor__note--muted {
  color: var(--text-muted);
}

:root[data-theme='dark'] .email-editor__actions {
  border-top-color: var(--border-light);
}

:root[data-theme='dark'] .email-editor :deep(.rich-editor-container) {
  background-color: var(--surface-elevated);
  border-color: var(--border-light);
}

:root[data-theme='dark'] .email-editor :deep(.rich-editor-toolbar) {
  background-color: var(--surface-elevated);
  border-bottom-color: var(--border-light);
}

:root[data-theme='dark'] .email-editor :deep(.toolbar-btn) {
  color: var(--text-muted);
}

:root[data-theme='dark'] .email-editor :deep(.toolbar-btn:hover:not(:disabled)),
:root[data-theme='dark'] .email-editor :deep(.dropdown-item:hover) {
  background-color: var(--border-light);
  color: var(--charcoal);
}

:root[data-theme='dark'] .email-editor :deep(.toolbar-btn.active),
:root[data-theme='dark'] .email-editor :deep(.dropdown-item.active) {
  background-color: rgba(96, 165, 250, 0.18);
  color: var(--info);
}

:root[data-theme='dark'] .email-editor :deep(.toolbar-sep),
:root[data-theme='dark'] .email-editor :deep(.email-look-sep) {
  background-color: var(--border-light);
}

:root[data-theme='dark'] .email-editor :deep(.heading-dropdown-menu) {
  background: var(--surface-elevated);
  border-color: var(--border-light);
}

:root[data-theme='dark'] .email-editor :deep(.dropdown-item) {
  color: var(--charcoal);
}

:root[data-theme='dark'] .email-editor :deep(.table-context-bar) {
  background-color: rgba(96, 165, 250, 0.12);
  border-bottom-color: var(--border-light);
}

:root[data-theme='dark'] .email-editor :deep(.table-context-heading),
:root[data-theme='dark'] .email-editor :deep(.table-context-title),
:root[data-theme='dark'] .email-editor :deep(.table-action-btn:not(.danger)) {
  color: var(--info);
}

:root[data-theme='dark'] .email-editor :deep(.raw-html-textarea),
:root[data-theme='dark'] .email-editor :deep(.tiptap.ProseMirror),
:root[data-theme='dark'] .email-editor :deep(.tiptap.ProseMirror h1),
:root[data-theme='dark'] .email-editor :deep(.tiptap.ProseMirror h2),
:root[data-theme='dark'] .email-editor :deep(.tiptap.ProseMirror h3),
:root[data-theme='dark'] .email-editor :deep(.tiptap.ProseMirror h4) {
  color: var(--charcoal);
}

:root[data-theme='dark'] .email-editor :deep(.tiptap.ProseMirror blockquote) {
  color: var(--text-muted);
  border-left-color: var(--border-light);
}

:root[data-theme='dark'] .email-editor :deep(.tiptap.ProseMirror a) {
  color: var(--info);
}

:root[data-theme='dark'] .email-editor :deep(.tiptap.ProseMirror code),
:root[data-theme='dark'] .email-editor :deep(.tiptap.ProseMirror th) {
  background-color: var(--border-light);
}

:root[data-theme='dark'] .email-editor :deep(.tiptap.ProseMirror th),
:root[data-theme='dark'] .email-editor :deep(.tiptap.ProseMirror td) {
  border-color: var(--border-light);
}

:root[data-theme='dark'] .email-editor :deep(.tiptap.ProseMirror hr) {
  border-top-color: var(--border-light);
}

/* The email's own boxes keep their light backgrounds, so their text stays
   dark and their links blue. */
:root[data-theme='dark'] .email-editor :deep(.tiptap.ProseMirror .email-box) {
  color: #1f2937;
}

:root[data-theme='dark'] .email-editor :deep(.tiptap.ProseMirror .email-box a:not([style])) {
  color: #2563eb;
}
</style>
