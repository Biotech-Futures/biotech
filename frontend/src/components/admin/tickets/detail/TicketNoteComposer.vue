<template>
  <!-- The note side of TicketComposer.vue, whose tab names it and whose box
       turns amber while it is open. -->
  <form class="note-box" @submit.prevent="submit">
    <textarea
      ref="textarea"
      v-model="body"
      class="note-box__text"
      aria-label="Internal note, not visible to the requester"
      :aria-describedby="hintId"
      :maxlength="MAX_BODY_LENGTH"
      rows="3"
      placeholder="Visible to support only. No email is sent and the requester's ticket shows no change."
      :readonly="isSending"
    ></textarea>
    <!-- The designer's line, said once more under the words themselves. -->
    <p :id="hintId" class="note-box__hint">
      <TicketIcon name="lock" :size="12" />
      Only support can see this. The requester is not emailed.
    </p>

    <div class="note-box__footer">
      <!-- The visible frame, the lock and the wording all say which of the two
           boxes this is; none of that reaches a screen reader through the file
           input, which had no accessible name of its own. See the matching
           note in TicketReplyComposer.vue. -->
      <input
        ref="fileInput"
        type="file"
        multiple
        class="note-box__files"
        aria-label="Attach files to this internal note"
        :accept="ACCEPTED_FILES"
        :disabled="isSending"
        @change="onFiles"
      />
      <!-- The same list as the reply box, in this box's amber, with the same
           Replace and Remove on every file. -->
      <ul v-if="files.length" class="note-box__chosen" aria-label="Files attached to this internal note">
        <li v-for="(file, index) in files" :key="`${file.name}-${index}`" class="note-box__chip">
          <TicketIcon name="file" :size="13" />
          <span class="note-box__chip-name">{{ file.name }}</span>
          <button
            type="button"
            class="note-box__chip-replace"
            :aria-label="`Replace ${file.name}`"
            :disabled="isSending"
            @click="startReplace(index)"
          >
            Replace
          </button>
          <button
            type="button"
            class="note-box__chip-remove"
            :aria-label="`Remove ${file.name}`"
            :disabled="isSending"
            @click="removeFile(index)"
          >
            <TicketIcon name="x" :size="12" />
          </button>
        </li>
      </ul>
      <span v-else class="note-box__none" aria-hidden="true">No file chosen</span>
      <input
        ref="replaceInput"
        type="file"
        class="note-box__replace"
        tabindex="-1"
        aria-hidden="true"
        :accept="ACCEPTED_FILES"
        @change="onReplace"
      />
      <!-- One group, so that when the files push the row onto a second line
           the counter and the button go together and stay on the right. -->
      <div class="note-box__actions">
        <span class="note-box__counter">{{ body.length }}/{{ MAX_BODY_LENGTH }}</span>
        <button
          ref="sendButton"
          type="submit"
          class="note-box__send"
          :disabled="isSending || !body.trim()"
        >
          {{ isSending ? 'Saving…' : 'Add internal note' }}
        </button>
      </div>
    </div>

    <p v-if="error" class="note-box__error" role="alert">{{ error }}</p>
  </form>
</template>

<script setup lang="ts">
import { useId } from 'vue'

import TicketIcon from '@/components/support/TicketIcon.vue'
import '@/components/support/ticketControls.css'

import { ACCEPTED_FILES, MAX_BODY_LENGTH, useMessageComposer } from './useMessageComposer'

/**
 * Deliberately does not look like the reply box.
 *
 * The two sides of one box do opposite things: one is read by a student, the
 * other must never be. The amber ground, the lock and the wording are all
 * there so that telling them apart does not depend on reading a label
 * carefully at the end of a long shift.
 */
const props = defineProps<{
  /** Resolves when the note is stored. Rejects, so a failed send keeps what
   *  was typed instead of throwing it away. Two arguments only: a note must
   *  never move the ticket, so there is no way to pass moveToPending here
   *  (the server refuses it on a note too). */
  send: (body: string, files: File[]) => Promise<unknown>
}>()

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
} = useMessageComposer((text, files) => props.send(text, files))

const hintId = useId()
</script>

<style scoped>
/* The note side of the box in TicketComposer.vue, which paints the amber
   ground (#fff8e6, dark #2a2516) these were measured on. The second redesign
   round (D2-16) moves the marking from a dashed frame round this box to the
   whole box's colour, and draws the controls in it as plain as the reply
   side's, with the button an outline. Measured (WCAG AA: 4.5:1 for text, 3:1
   for a control's edge):
     light  hint #8a5a00 5.59   muted #5a6268 5.86   field edge #84938f 3.03
            (3.21 against the white field)
     dark   hint #fbbf24 9.15   muted #a3b3ae 7.00   field edge #70827d 3.77
   The button is an outline on its own ground, #174243 on #ffffff 11.07 and
   #e6efed on #1d2826 12.96 in dark: he drew it only greyed out, and this is
   what greys to what he drew. */
.note-box {
  --note-ink: #8a5a00;
  --note-edge: #84938f;
  --note-muted: #5a6268;
  --note-control: #ffffff;
  --note-placeholder: #6c757d;

  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

:root[data-theme='dark'] .note-box {
  --note-ink: #fbbf24;
  --note-edge: #70827d;
  --note-muted: #a3b3ae;
  --note-control: #1d2826;
  --note-placeholder: #93a39e;
}

/* 84px, three lines, as both sides of the box are drawn. A hair less on
   the right than the left: the note's placeholder fills one line in the
   designer's box with 1.5px to spare, and wrapped here at 12px. */
.note-box__text {
  width: 100%;
  height: 5.25rem;
  padding: 0.625rem 0.625rem 0.625rem 0.75rem;
  border: 1px solid var(--note-edge);
  border-radius: 8px;
  background: var(--white);
  color: var(--teal);
  font-family: inherit;
  font-size: 0.95rem;
  line-height: 1.45;
  resize: vertical;
}

.note-box__text::placeholder {
  color: var(--note-placeholder);
  opacity: 1;
}

.note-box__text[readonly] {
  opacity: 0.8;
}

.note-box__hint {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  margin: 0;
  color: var(--note-ink);
  font-size: 0.8rem;
  font-weight: 700;
  line-height: 1.2;
}

.note-box__footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.6rem;
}

/* The same button as TicketReplyComposer.vue's: the browser's own, cut to
   its width, the words it prints after it made transparent. */
.note-box__files {
  width: 8.4rem;
  max-width: 100%;
  overflow: hidden;
  color: transparent;
  font-size: 0.85rem;
}

.note-box__files::file-selector-button {
  height: 2rem;
  margin: 0;
  padding: 0 0.75rem 0 2rem;
  border: 1px solid var(--note-edge);
  border-radius: 8px;
  background: var(--note-control) var(--ticket-paperclip) no-repeat 0.7rem center;
  color: var(--teal);
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}

.note-box__files:disabled::file-selector-button {
  opacity: 0.55;
  cursor: not-allowed;
}

.note-box__none {
  font-size: 0.85rem;
  color: var(--note-muted);
}

.note-box__chosen {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.note-box__chip {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.1rem 0.3rem 0.1rem 0.7rem;
  border: 1px solid var(--note-ink);
  border-radius: 999px;
  color: var(--note-ink);
  font-size: 0.82rem;
  font-weight: 700;
  overflow-wrap: anywhere;
}

/* As in TicketReplyComposer.vue, in the note's ink: #8a5a00 on #fff8e6 is
   5.59:1, dark #fbbf24 on #2a2516 9.15:1. */
.note-box__chip-replace,
.note-box__chip-remove {
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

.note-box__chip-replace {
  font-size: 0.78rem;
  text-decoration: underline;
}

.note-box__chip-remove {
  min-width: 1.5rem;
  padding: 0;
}

.note-box__chip-replace:disabled,
.note-box__chip-remove:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.note-box__replace {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}

.note-box__actions {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-left: auto;
}

.note-box__counter {
  font-size: 0.78rem;
  color: var(--note-muted);
}

.note-box__send {
  min-height: 2.5rem;
  padding: 0 1.125rem;
  border: 1px solid var(--note-edge);
  border-radius: 8px;
  background: var(--note-control);
  color: var(--teal);
  font-family: inherit;
  font-weight: 600;
  font-size: 0.9rem;
  cursor: pointer;
}

.note-box__send:hover:not(:disabled) {
  border-color: var(--teal);
}

.note-box__send:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.note-box__error {
  margin: 0;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--note-ink);
}
</style>
