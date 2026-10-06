<template>
  <form class="note-box" :aria-labelledby="headingId" @submit.prevent="submit">
    <p :id="headingId" class="note-box__heading">
      <TicketIcon name="lock" :size="14" />
      Internal note: the requester never sees this
    </p>
    <textarea
      ref="textarea"
      v-model="body"
      class="note-box__text"
      aria-label="Internal note, not visible to the requester"
      :maxlength="MAX_BODY_LENGTH"
      rows="3"
      placeholder="Visible to support only. No email is sent and the requester's ticket shows no change."
      :readonly="isSending"
    ></textarea>

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
      <!-- The same picked-files line as the reply box, in this box's amber.
           Hidden from a screen reader, which hears the input itself. -->
      <ul v-if="files.length" class="note-box__chosen" aria-hidden="true">
        <li v-for="(file, index) in files" :key="`${file.name}-${index}`" class="note-box__chip">
          <TicketIcon name="file" :size="13" />
          <span>{{ file.name }}</span>
        </li>
      </ul>
      <span v-else class="note-box__none" aria-hidden="true">No file chosen</span>
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
 * These two controls sit next to each other and do opposite things: one is
 * read by a student, the other must never be. The amber frame, the lock and
 * the wording are all there so that telling them apart does not depend on
 * reading a label carefully at the end of a long shift.
 */
const props = defineProps<{
  /** Resolves when the note is stored. Rejects, so a failed send keeps what
   *  was typed instead of throwing it away. Two arguments only: a note must
   *  never move the ticket, so there is no way to pass moveToPending here
   *  (the server refuses it on a note too). */
  send: (body: string, files: File[]) => Promise<unknown>
}>()

const { body, files, isSending, error, textarea, fileInput, sendButton, onFiles, submit } =
  useMessageComposer((text, files) => props.send(text, files))

const headingId = useId()
</script>

<style scoped>
/* The same amber as the internal-note rows in the timeline, a shade deeper
   since the first redesign round (October 2026). Measured:
     light  ink #78350f on #fffbeb 8.75, on the #ffffff textarea 9.07,
            border #b45309 on #fffbeb 4.84 (non-text, needs 3:1)
     dark   ink #fbbf24 on #2b2410 9.23, on the --white textarea 10.08,
            border #d08a1e on #2b2410 5.38
   The button is a deep amber with white words in light, #fff on #92400e
   7.09 (the designer drew it only greyed out; this is the colour that greys
   to what he drew), and the ink on the ground reversed in dark, #2b2410 on
   #fbbf24 9.23. */
.note-box {
  --note-ground: #fffbeb;
  --note-border: #b45309;
  --note-ink: #78350f;
  --note-button: #92400e;
  --note-on-button: #ffffff;
  --note-placeholder: #6c757d;

  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  padding: 0.875rem 1.125rem;
  border: 2px dashed var(--note-border);
  border-radius: 12px;
  background: var(--note-ground);
  color: var(--note-ink);
}

:root[data-theme='dark'] .note-box {
  --note-ground: #2b2410;
  --note-border: #d08a1e;
  --note-ink: #fbbf24;
  --note-button: #fbbf24;
  --note-on-button: #2b2410;
  --note-placeholder: #93a39e;
}

.note-box__heading {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0;
  font-size: 0.95rem;
  font-weight: 700;
}

.note-box__text {
  width: 100%;
  padding: 0.55rem 0.875rem;
  border: 1px solid var(--note-border);
  border-radius: 8px;
  background: var(--white);
  color: var(--charcoal);
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
  border: 1px solid var(--note-border);
  border-radius: 8px;
  background: var(--white) var(--ticket-paperclip) no-repeat 0.7rem center;
  color: var(--charcoal);
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
  color: var(--note-ink);
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
  padding: 0.2rem 0.7rem;
  border: 1px solid var(--note-ink);
  border-radius: 999px;
  color: var(--note-ink);
  font-size: 0.82rem;
  font-weight: 700;
  overflow-wrap: anywhere;
}

.note-box__counter {
  margin-left: auto;
  font-size: 0.78rem;
  color: var(--note-ink);
}

.note-box__send {
  min-height: 2.5rem;
  padding: 0 1.125rem;
  border: none;
  border-radius: 8px;
  background: var(--note-button);
  color: var(--note-on-button);
  font-weight: 600;
  font-size: 0.9rem;
  cursor: pointer;
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
