<template>
  <form class="reply-box" :aria-labelledby="headingId" @submit.prevent="onSubmit">
    <p :id="headingId" class="reply-box__heading">Reply to the requester</p>
    <!-- Named on the element: the heading above is visible but a textarea
         does not take its name from a nearby paragraph. -->
    <textarea
      ref="textarea"
      v-model="body"
      class="reply-box__text"
      aria-label="Reply to the requester"
      :maxlength="MAX_BODY_LENGTH"
      rows="3"
      placeholder="This goes to the person who raised the ticket, and they are emailed about it."
      :readonly="isSending"
    ></textarea>

    <div class="reply-box__pending">
      <input
        :id="checkboxId"
        v-model="moveToPending"
        type="checkbox"
        class="reply-box__checkbox"
        :disabled="isSending"
      />
      <label :for="checkboxId">I have asked them for something. Wait for their reply.</label>
    </div>

    <div class="reply-box__footer">
      <!-- A bare file input computes to an empty name: the "Choose File" text
           belongs to a button inside the browser's own shadow DOM, so a screen
           reader announces the same thing for both pickers in this panel. One
           attaches to a reply the student is emailed; the other attaches to a
           note they must never see. -->
      <input
        ref="fileInput"
        type="file"
        multiple
        class="reply-box__files"
        aria-label="Attach files to this reply"
        :accept="ACCEPTED_FILES"
        :disabled="isSending"
        @change="onFiles"
      />
      <!-- What will be sent, a pill per file, each with its own Replace and
           Remove. The input is emptied after every pick, so this list is the
           only record of the files and a screen reader reads it here. -->
      <ul v-if="files.length" class="reply-box__chosen" aria-label="Files attached to this reply">
        <li v-for="(file, index) in files" :key="`${file.name}-${index}`" class="reply-box__chip">
          <TicketIcon name="file" :size="13" />
          <span class="reply-box__chip-name">{{ file.name }}</span>
          <button
            type="button"
            class="reply-box__chip-replace"
            :aria-label="`Replace ${file.name}`"
            :disabled="isSending"
            @click="startReplace(index)"
          >
            Replace
          </button>
          <button
            type="button"
            class="reply-box__chip-remove"
            :aria-label="`Remove ${file.name}`"
            :disabled="isSending"
            @click="removeFile(index)"
          >
            <TicketIcon name="x" :size="12" />
          </button>
        </li>
      </ul>
      <span v-else class="reply-box__none" aria-hidden="true">No file chosen</span>
      <!-- Behind every Replace button, for one file. Out of the tab order and
           hidden from screen readers: the button that opens it names the file
           it replaces. -->
      <input
        ref="replaceInput"
        type="file"
        class="reply-box__replace"
        tabindex="-1"
        aria-hidden="true"
        :accept="ACCEPTED_FILES"
        @change="onReplace"
      />
      <!-- One group, so that when the files push the row onto a second line
           the counter and the button go together and stay on the right. -->
      <div class="reply-box__actions">
        <span class="reply-box__counter">{{ body.length }}/{{ MAX_BODY_LENGTH }}</span>
        <button
          ref="sendButton"
          type="submit"
          class="reply-box__send"
          :disabled="isSending || !body.trim()"
        >
          {{ isSending ? 'Sending…' : 'Send reply' }}
        </button>
      </div>
    </div>

    <p v-if="error" class="reply-box__error" role="alert">{{ error }}</p>
  </form>
</template>

<script setup lang="ts">
import { ref, useId } from 'vue'

import TicketIcon from '@/components/support/TicketIcon.vue'
import '@/components/support/ticketControls.css'

import { ACCEPTED_FILES, MAX_BODY_LENGTH, useMessageComposer } from './useMessageComposer'

const props = defineProps<{
  /** Resolves when the reply is stored. Rejects, so a failed send keeps what
   *  was typed instead of throwing it away. */
  send: (body: string, files: File[], moveToPending: boolean) => Promise<unknown>
}>()

// Off by default: most replies are an answer, not a question.
//
// Ticked, it travels on the SAME request as the reply (moveToPending), never
// as a status change after it. The reply email reads the status at send time
// to choose its wording, so a reply followed by a separate PATCH went out
// saying the opposite of what the agent meant.
const moveToPending = ref(false)

const {
  body,
  files,
  isSending,
  error,
  textarea,
  fileInput,
  replaceInput,
  sendButton,
  onFiles,
  removeFile,
  startReplace,
  onReplace,
  submit
} = useMessageComposer((text, files) => props.send(text, files, moveToPending.value))

const headingId = useId()
const checkboxId = useId()

async function onSubmit() {
  if (await submit()) moveToPending.value = false
}
</script>

<style scoped>
/* A plain box on the panel, a step greyer than the panel itself since the
   first redesign round (October 2026). The note box next to it is the one
   that is marked; this one stays ordinary on purpose. Text on green is a
   literal #fff (6.03:1): --white is a surface token and turns dark green in
   the dark theme (U1 5.3). Measured (WCAG AA: 4.5:1 for text, 3:1 for a
   control's edge):
     light  muted #5a6268 on the #f8f9fa box 5.89   field edge #84938f 3.04
            placeholder #6c757d on the white field 4.69   file pill #017151 5.72
     dark   muted #a3b3ae on the #161f1d box 7.71   field edge #70827d 4.15
            placeholder #93a39e 6.39   file pill #5ea99e 6.13 */
.reply-box {
  --reply-muted: #5a6268;
  --reply-danger: #a71d2a;
  --reply-ground: #f8f9fa;
  --reply-frame: #e3e7e5;
  --reply-edge: #84938f;
  --reply-placeholder: #6c757d;
  --reply-file: #017151;

  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  padding: 0.875rem 1.125rem;
  border: 1px solid var(--reply-frame);
  border-radius: 12px;
  background: var(--reply-ground);
  color: var(--charcoal);
}

:root[data-theme='dark'] .reply-box {
  --reply-muted: #a3b3ae;
  --reply-danger: var(--danger);
  --reply-ground: #161f1d;
  --reply-frame: #2b3936;
  --reply-edge: #70827d;
  --reply-placeholder: #93a39e;
  --reply-file: #5ea99e;
}

.reply-box__heading {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
}

.reply-box__text {
  width: 100%;
  padding: 0.55rem 0.875rem;
  border: 1px solid var(--reply-edge);
  border-radius: 8px;
  background: var(--white);
  color: var(--charcoal);
  font-family: inherit;
  font-size: 0.95rem;
  line-height: 1.45;
  resize: vertical;
}

.reply-box__text::placeholder {
  color: var(--reply-placeholder);
  opacity: 1;
}

.reply-box__text[readonly] {
  opacity: 0.8;
}

.reply-box__pending {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  font-size: 0.9rem;
}

/* The browser's own box, a little bigger, ticked in brand green. */
.reply-box__checkbox {
  width: 1rem;
  height: 1rem;
  margin: 0;
  accent-color: #017151;
}

.reply-box__footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.6rem;
}

/* Only the browser's button shows: the input is cut to its width and the
   words it prints after it are made transparent, since the line beside it
   says the same. The paperclip is a background, as the pseudo-element holds
   no element. Same button as TicketNoteComposer.vue's. */
.reply-box__files {
  width: 8.4rem;
  max-width: 100%;
  overflow: hidden;
  color: transparent;
  font-size: 0.85rem;
}

.reply-box__files::file-selector-button {
  height: 2rem;
  margin: 0;
  padding: 0 0.75rem 0 2rem;
  border: 1px solid var(--reply-edge);
  border-radius: 8px;
  background: var(--white) var(--ticket-paperclip) no-repeat 0.7rem center;
  color: var(--charcoal);
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}

.reply-box__files:disabled::file-selector-button {
  opacity: 0.55;
  cursor: not-allowed;
}

.reply-box__none {
  font-size: 0.85rem;
  color: var(--reply-muted);
}

.reply-box__chosen {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.reply-box__chip {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.1rem 0.3rem 0.1rem 0.7rem;
  border: 1px solid var(--reply-file);
  border-radius: 999px;
  color: var(--reply-file);
  font-size: 0.82rem;
  font-weight: 700;
  overflow-wrap: anywhere;
}

/* Both 24px high, the target size WCAG 2.2 asks for, in the pill's own
   colour: #017151 on the #f8f9fa box is 5.72:1, dark #5ea99e on #161f1d
   6.13:1. Replace is a word, underlined so it reads as an action rather than
   part of the name; no picture says "replace" without one. */
.reply-box__chip-replace,
.reply-box__chip-remove {
  display: inline-flex;
  flex: none;
  align-items: center;
  justify-content: center;
  min-height: 1.5rem;
  padding: 0 0.3rem;
  border: none;
  border-radius: 6px;
  background: none;
  color: inherit;
  font: inherit;
  cursor: pointer;
}

.reply-box__chip-replace {
  font-size: 0.78rem;
  text-decoration: underline;
}

.reply-box__chip-remove {
  min-width: 1.5rem;
  padding: 0;
}

.reply-box__chip-replace:disabled,
.reply-box__chip-remove:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.reply-box__replace {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.reply-box__actions {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-left: auto;
}

.reply-box__counter {
  font-size: 0.78rem;
  color: var(--reply-muted);
}

.reply-box__send {
  min-height: 2.5rem;
  padding: 0 1.125rem;
  border: none;
  border-radius: 8px;
  background: #017151;
  color: #fff;
  font-weight: 600;
  font-size: 0.9rem;
  cursor: pointer;
}

.reply-box__send:hover:not(:disabled) {
  background: #015a41;
}

.reply-box__send:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.reply-box__error {
  margin: 0;
  color: var(--reply-danger);
  font-size: 0.85rem;
}
</style>
