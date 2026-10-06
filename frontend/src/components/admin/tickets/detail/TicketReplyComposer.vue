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
      rows="4"
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

    <p v-if="error" class="reply-box__error" role="alert">{{ error }}</p>
  </form>
</template>

<script setup lang="ts">
import { ref, useId } from 'vue'

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

const { body, isSending, error, textarea, fileInput, sendButton, onFiles, submit } =
  useMessageComposer((text, files) => props.send(text, files, moveToPending.value))

const headingId = useId()
const checkboxId = useId()

async function onSubmit() {
  if (await submit()) moveToPending.value = false
}
</script>

<style scoped>
/* Plain frame on the panel's own ground. The note box next to it is the one
   that is marked; this one stays ordinary on purpose. Text on green is a
   literal #fff (6.03:1): --white is a surface token and turns dark green in
   the dark theme (U1 5.3). Muted text is #616970, 5.58:1 on #ffffff; dark
   hands it back to --text-muted, 5.72:1 on #161f1d. */
.reply-box {
  --reply-muted: #616970;
  --reply-danger: #a71d2a;

  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  padding: 0.9rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--white);
  color: var(--charcoal);
}

:root[data-theme='dark'] .reply-box {
  --reply-muted: var(--text-muted);
  --reply-danger: var(--danger);
}

.reply-box__heading {
  margin: 0;
  font-size: 0.92rem;
  font-weight: 600;
}

.reply-box__text {
  width: 100%;
  padding: 0.55rem 0.7rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--white);
  color: var(--charcoal);
  font-family: inherit;
  font-size: 0.92rem;
  resize: vertical;
}

.reply-box__text[readonly] {
  opacity: 0.8;
}

.reply-box__pending {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
}

.reply-box__footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.6rem;
}

.reply-box__files {
  max-width: 16rem;
  font-size: 0.8rem;
  color: var(--reply-muted);
}

.reply-box__counter {
  margin-left: auto;
  font-size: 0.78rem;
  color: var(--reply-muted);
}

.reply-box__send {
  padding: 0.45rem 1rem;
  border: none;
  border-radius: 6px;
  background: #017151;
  color: #fff;
  font-weight: 600;
  font-size: 0.88rem;
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
