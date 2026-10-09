<template>
  <section class="email-editor" aria-label="Email editor">
    <header class="email-editor__header">
      <div class="email-editor__title-block">
        <h2 class="email-editor__title">
          <span>
            {{ nameParts(emailTemplate.name).title }}
            <span v-if="nameParts(emailTemplate.name).to" class="email-editor__to">
              {{ nameParts(emailTemplate.name).to }}
            </span>
          </span>
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

    <p v-if="emailTemplate.delivery" class="email-editor__delivery" data-test="delivery">
      <i class="fas fa-users" aria-hidden="true"></i>
      {{ emailTemplate.delivery }}
    </p>

    <!-- The mailbox it goes from: only those the server can sign in to, since
         Hostinger rejects a From that isn't the signed-in mailbox or one of
         its aliases. Saved at once, like the on/off switch. -->
    <div class="editor__field">
      <label class="editor__label" :for="`${emailTemplate.key}-sender`">Send from</label>
      <select
        :id="`${emailTemplate.key}-sender`"
        class="editor__title email-editor__sender"
        :value="emailTemplate.sender"
        :disabled="busy"
        @change="emit('change-sender', ($event.target as HTMLSelectElement).value)"
      >
        <option v-for="sender in emailTemplate.senders" :key="sender.key" :value="sender.key">
          {{ sender.address }}
        </option>
      </select>
    </div>

    <!-- Tags go into whichever of Subject or Body was used last. -->
    <div class="editor__field">
      <span class="editor__label">Placeholders</span>
      <MergeTagPalette :tags="emailTemplate.mergeTags" @insert="onInsertTag" />
    </div>

    <div class="editor__field">
      <label class="editor__label" for="template-subject">Subject</label>
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
        class="editor__title"
        :value="subject"
        :placeholder="emailTemplate.defaultSubject"
        :disabled="saving || restoring"
        maxlength="255"
        @focus="activeField = 'subject'"
        @input="emit('update:subject', ($event.target as HTMLInputElement).value)"
      />
    </div>

    <div class="editor__field email-editor__body-field">
      <label class="editor__label">Body</label>
      <!-- Like Subject, read-only only while its wording is being written: a
           read-only editor drops its toolbar, which flashed on quick saves like
           Send from. -->
      <div class="email-editor__body" @focusin="activeField = 'body'">
        <RichEditor
          ref="bodyEditor"
          :model-value="body"
          email-mode
          compact
          :link-placeholders="linkPlaceholders"
          :read-only="saving || restoring"
          @update:model-value="emit('update:body', $event)"
          @focus="activeField = 'body'"
        />
      </div>
    </div>

    <footer class="editor__actions">
      <div class="editor__actions-primary">
        <button type="button" class="btn btn-primary btn-sm" :disabled="!dirty || busy" @click="emit('save')">
          {{ saving ? 'Saving…' : 'Save changes' }}
        </button>
        <button
          type="button"
          class="btn btn-outline btn-sm"
          :disabled="!emailTemplate.usingSavedContent || busy"
          @click="emit('restore')"
        >
          {{ restoring ? 'Restoring…' : 'Restore default' }}
        </button>
      </div>

      <!-- Send the email as it stands to any address, as the group or person
           picked would get it (sample values when nobody is picked). The
           preview shows the one picked too. -->
      <div
        class="email-editor__test"
        :class="{ 'email-editor__test--of': testRecipientsFailed || testRecipients }"
        data-test="test-email"
      >
        <!-- A critical email (sign-in, passwords) can't be test sent. -->
        <button
          type="button"
          class="btn btn-outline btn-sm"
          :disabled="emailTemplate.locked || busy || testRecipientsLoading || !testTo.trim()"
          :title="emailTemplate.locked ? lockedTestReason : undefined"
          @click="sendTest"
        >
          <i v-if="emailTemplate.locked" class="fas fa-lock email-editor__test-button-lock" aria-hidden="true"></i>
          {{ testing ? 'Sending…' : 'Send Test' }}
        </button>
        <template v-if="testRecipientsFailed || testRecipients">
          <span class="email-editor__test-word">of</span>
          <!-- Open even on a critical email, so its preview can show anyone. -->
          <select
            v-model="testOf"
            class="email-editor__test-select"
            aria-label="Send it as"
            data-test="test-of"
            :disabled="!testRecipients?.length"
          >
            <option v-if="!testRecipients?.length" value="">
              {{ testRecipientsFailed ? "Couldn't load the list" : 'Nobody yet (sample details)' }}
            </option>
            <option v-for="option in testRecipients" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </template>
        <span class="email-editor__test-word email-editor__test-word--to">to</span>
        <!-- Password managers leave this box alone. -->
        <input
          v-model="testTo"
          type="email"
          class="email-editor__test-to"
          placeholder="Email address"
          aria-label="Send the test to"
          autocomplete="off"
          data-bwignore
          data-1p-ignore
          data-lpignore="true"
          @keydown.enter.prevent="sendTest"
        />
        <span
          v-if="testResult"
          class="email-editor__test-result"
          :class="testResult.ok ? 'email-editor__test-result--ok' : 'email-editor__test-result--error'"
          role="status"
        >
          {{ testResult.text }}
        </span>
      </div>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, ref } from 'vue'
import MergeTagPalette from '@/components/admin/emails/MergeTagPalette.vue'
import { isLinkPlaceholder } from '@/components/admin/emailBlocks'
import {
  mergeTagToken,
  nameParts,
  type SystemEmailMergeTag,
  type SystemEmailTemplate,
  type SystemEmailTestRecipient
} from '@/utils/systemEmail'
import { useAuthStore } from '@/stores/auth'

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
  /** How the last test send went. */
  testResult?: { ok: boolean; text: string } | null
  /** Who a test can be "of": null when the email has nothing of a person's own. */
  testRecipients?: SystemEmailTestRecipient[] | null
  testRecipientsLoading?: boolean
  testRecipientsFailed?: boolean
}>()

// The one picked: the test and the preview carry their details.
const testOf = defineModel<string>('testOf', { default: '' })

// Where a test goes: the admin's own address to start with.
const auth = useAuthStore()
const testTo = ref(auth.user?.email ?? '')

// Why a critical email's test is locked, shown on hover.
const lockedTestReason = computed(() => `${props.emailTemplate.name} is critical, so it can't be test sent`)

const sendTest = () => {
  if (props.emailTemplate.locked || props.busy || props.testRecipientsLoading || !testTo.value.trim()) return
  emit('test-send', testTo.value.trim())
}

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
  (e: 'change-sender', sender: string): void
  (e: 'save'): void
  (e: 'restore'): void
  (e: 'test-send', to: string): void
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

/* No line above the buttons here: on System Emails it sits above Preview
   instead (EmailPreview). */
.email-editor .editor__actions {
  border-top: none;
}

/* Send Test Email of someone to an address, as on the Management pages' email tabs. */
/* The button, then "of" and its list, then "to" and the address on the line
   below, lined up under "of". Without a list, "to" sits beside the button. */
.email-editor__test {
  display: grid;
  /* At least 13rem, taking the room there is up to the wider of the
     address box and the longest name. */
  grid-template-columns: auto auto minmax(13rem, max-content);
  align-items: center;
  gap: 0.5rem;
}

.email-editor__test-word {
  color: var(--text-muted);
  font-size: 0.85rem;
}

.email-editor__test--of .email-editor__test-word--to {
  grid-column: 2;
}

.email-editor__test-select,
.email-editor__test-to {
  border: 1px solid var(--border-light);
  border-radius: 6px;
  padding: 0.3rem 0.5rem;
  font-size: 0.85rem;
  font-family: inherit;
  background: var(--surface-elevated);
  color: var(--charcoal);
}

/* As wide as the address box, or wider when a name needs it, up to 25rem. */
.email-editor__test-select {
  width: 100%;
  max-width: 25rem;
}

.email-editor__test-button-lock {
  margin-right: 0.25rem;
  font-size: 0.75em;
}


.email-editor__test-to {
  /* 17rem, narrowing to 13rem when room is short. */
  width: 17rem;
  max-width: 100%;
}

.email-editor__test-select:focus,
.email-editor__test-to:focus {
  outline: none;
  border-color: var(--dark-green);
}

.email-editor__test-result {
  font-size: 0.85rem;
  /* Its own line, so it never pushes the address box down. */
  grid-column: 1 / -1;
}

.email-editor__test-result--ok {
  color: var(--dark-green);
}

.email-editor__test-result--error {
  color: var(--danger);
}

/* The Body box stops at 670px, however wide the page is. */
.email-editor__body-field {
  width: 100%;
  max-width: 670px;
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

/* Who it goes to, as in "(to student)": not bold, and lighter. */
.email-editor__to {
  font-weight: 400;
  color: var(--text-muted);
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

/* Who a group's email goes to: plain, like the description. */
.email-editor__delivery {
  display: flex;
  align-items: center;
  gap: 0.5rem;
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

/* As wide as its addresses, not the whole column. */
.email-editor__sender {
  width: auto;
  min-width: 16rem;
  background: var(--surface-elevated, #fff);
}

.email-editor__last-edited {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  /* The same space as below it, the editor's 1rem gap. */
  margin: 1rem 0 0;
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

/* Dark theme: the subject and body editor take the grey other pages give
   their boxes, with light text. */
:root[data-theme='dark'] .email-editor__title {
  color: var(--charcoal);
}

:root[data-theme='dark'] .email-editor__switch-label {
  color: var(--text-muted);
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

:root[data-theme='dark'] .email-editor :deep(.raw-html-textarea) {
  color: var(--charcoal);
}

/* The writing area stays white, like the email itself, so the template's own
   text colours read as they will in the inbox. */
:root[data-theme='dark'] .email-editor :deep(.rich-editor-content-area),
:root[data-theme='dark'] .email-editor :deep(.tiptap.ProseMirror) {
  background-color: #ffffff;
}
</style>

<!-- The title box, fields and button bar the announcement editors share. -->
<style scoped src="../editorForm.css"></style>
