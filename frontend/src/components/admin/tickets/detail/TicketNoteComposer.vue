<template>
  <form class="note-box" :aria-labelledby="headingId" @submit.prevent="submit">
    <p :id="headingId" class="note-box__heading">
      <span aria-hidden="true">🔒</span>
      Internal note: the requester never sees this
    </p>
    <textarea
      ref="textarea"
      v-model="body"
      class="note-box__text"
      aria-label="Internal note, not visible to the requester"
      :maxlength="MAX_BODY_LENGTH"
      rows="4"
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

const { body, isSending, error, textarea, fileInput, sendButton, onFiles, submit } =
  useMessageComposer((text, files) => props.send(text, files))

const headingId = useId()
</script>

<style scoped>
/* The same amber as the internal-note rows in the timeline. Measured:
     light  ink #78350f on #fffbeb 8.75, on the #ffffff textarea 9.07,
            border #d97706 on #fffbeb 3.07 (non-text, needs 3:1)
     dark   ink #fbbf24 on #2b2410 9.23, on the --white textarea 10.08,
            border #b45309 on #2b2410 3.07
   The button is the ink on the ground, reversed: #fff on #78350f 9.07, and
   #2b2410 on #fbbf24 9.23 in dark. */
.note-box {
  --note-ground: #fffbeb;
  --note-border: #d97706;
  --note-ink: #78350f;
  --note-on-ink: #ffffff;

  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  padding: 0.9rem;
  border: 2px dashed var(--note-border);
  border-radius: 8px;
  background: var(--note-ground);
  color: var(--note-ink);
}

:root[data-theme='dark'] .note-box {
  --note-ground: #2b2410;
  --note-border: #b45309;
  --note-ink: #fbbf24;
  --note-on-ink: #2b2410;
}

.note-box__heading {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin: 0;
  font-size: 0.92rem;
  font-weight: 700;
}

.note-box__text {
  width: 100%;
  padding: 0.55rem 0.7rem;
  border: 1px solid var(--note-border);
  border-radius: 6px;
  background: var(--white);
  color: var(--charcoal);
  font-family: inherit;
  font-size: 0.92rem;
  resize: vertical;
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

.note-box__files {
  max-width: 16rem;
  font-size: 0.8rem;
  color: var(--note-ink);
}

.note-box__counter {
  margin-left: auto;
  font-size: 0.78rem;
  color: var(--note-ink);
}

.note-box__send {
  padding: 0.45rem 1rem;
  border: none;
  border-radius: 6px;
  background: var(--note-ink);
  color: var(--note-on-ink);
  font-weight: 600;
  font-size: 0.88rem;
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
