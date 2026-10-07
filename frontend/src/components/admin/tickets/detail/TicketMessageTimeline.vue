<template>
  <ol class="agent-timeline" aria-label="Conversation">
    <li
      v-for="message in messages"
      :key="message.id"
      class="agent-timeline__row"
      :class="{
        'agent-timeline__row--system': message.messageType === 'system',
        'agent-timeline__row--note': message.messageType === 'internal_note',
        'agent-timeline__row--requester': message.messageType === 'user_message',
        'agent-timeline__row--support': message.messageType === 'support_reply'
      }"
    >
      <!-- System lines sit centred and unattributed: the ticket telling its
           own story, not somebody speaking. The sentences are fixed on the
           server (services/system_messages.py). -->
      <p v-if="message.messageType === 'system'" class="agent-timeline__system">
        {{ message.body }} ·
        <time :datetime="message.createdAt">{{ when(message.createdAt) }}</time>
      </p>

      <!-- A message: name and time over it, the words in a bubble on the
           speaker's side (support on the right, the requester on the left,
           as the redesign draws it), files hanging underneath. An internal
           note is not a bubble: the whole row is its amber box. -->
      <div v-else class="agent-timeline__message">
        <p class="agent-timeline__meta">
          <span class="agent-timeline__author">{{ authorLabel(message) }}</span>
          <!-- The wall made visible: the same amber and lock the note box
               below uses, so a note already sent reads as one. The lock is
               hidden from screen readers, which hear "Internal note". -->
          <span v-if="message.messageType === 'internal_note'" class="agent-timeline__wall">
            <TicketIcon name="lock" :size="11" /> Internal note
          </span>
          <time class="agent-timeline__time" :datetime="message.createdAt">{{
            when(message.createdAt)
          }}</time>
        </p>
        <!-- Plain text, never v-html. Line breaks are part of what was typed. -->
        <div class="agent-timeline__bubble">
          <p class="agent-timeline__body">{{ message.body }}</p>
        </div>

        <ul v-if="message.attachments.length" class="agent-timeline__files">
          <li v-for="file in message.attachments" :key="file.id">
            <!-- A button, not a link. An anchor at the download endpoint is a
                 navigation the browser commits to before it knows the answer,
                 so a refusal replaces this app with DRF's error page and takes
                 the half-typed reply with it; with target="_blank" WebKit
                 leaks an empty tab per click instead. See
                 downloadTicketAttachment in utils/ticketAgentAPI.ts.

                 aria-disabled while the file is on its way, not disabled. A
                 browser moves focus off a button that becomes disabled, to the
                 page body and out of the modal panel. The guard in download()
                 is what ignores a second press. -->
            <button
              type="button"
              class="agent-timeline__file"
              :aria-disabled="busy[file.id] ? 'true' : undefined"
              @click="download(file)"
            >
              <TicketIcon name="paperclip" :size="14" />
              {{ file.filename }}
            </button>
            <span v-if="failed[file.id]" class="agent-timeline__file-error" role="alert">{{
              failed[file.id]
            }}</span>
          </li>
        </ul>
      </div>
    </li>
  </ol>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import TicketIcon from '@/components/support/TicketIcon.vue'
import { downloadTicketAttachment } from '@/utils/ticketAgentAPI'
import type { TicketAttachment, TicketMessage } from '@/utils/ticketAgentSchema'

import { authorLabel, downloadErrorMessage, when } from './ticketDetailText'

// Every type the server sends, internal notes included: this is the side of
// the wall that works in them (views_admin.py). ticket.body is NOT rendered
// separately; it is already the first user_message, with the original
// attachments, and a second copy would show the first message twice.
const props = defineProps<{ ticketId: number; messages: TicketMessage[] }>()

// Which files are in flight, and what went wrong with which one. Both keyed
// by attachment id: five files fit on a message, they are five separate
// answers, and a failure on one must not label another. Per-file rather than
// one global flag, or a click on the second file would do nothing while the
// first was still downloading.
//
// The React panel needed a useRef beside its busy state, because a React
// handler reads the state captured at the last render and two quick clicks
// both got past it. Here busy.value is read live from the reactive store, so
// the check below is a real guard on its own (the portal's TicketTimeline.vue
// does the same, and its test proves it).
const busy = ref<Record<number, boolean>>({})
const failed = ref<Record<number, string>>({})

function without<T>(map: Record<number, T>, id: number) {
  const next = { ...map }
  delete next[id]
  return next
}

async function download(file: TicketAttachment) {
  if (busy.value[file.id]) return
  busy.value = { ...busy.value, [file.id]: true }
  // A retry starts clean: the old error is about the last attempt.
  failed.value = without(failed.value, file.id)
  try {
    await downloadTicketAttachment(props.ticketId, file.id, file.filename)
  } catch (error) {
    // Deliberately not a redirect to the sign-in page on a 401 or 403.
    // Navigating is the thing this is here to stop: whatever is in the reply
    // box is still there, and it is the agent's.
    failed.value = { ...failed.value, [file.id]: downloadErrorMessage(error) }
  } finally {
    // In finally, or one click leaves the button marked busy for good.
    busy.value = without(busy.value, file.id)
  }
}
</script>

<style scoped>
/* The first redesign round (October 2026) gives the panel the student page's
   bubbles: support's own replies on the right in mint, the requester's on the
   left in white, name and time above, files hanging under, and a hairline
   either side of a system line. An internal note stays a full-width amber
   box with a solid label, never a bubble, so it cannot be mistaken for
   something the requester will read.

   Colours are literals where the token fails AA on this ground, measured with
   the WCAG formula on the panel (--white in light, #1d2826 in dark):

     light  muted #5a6268 6.21   error #a71d2a 7.36   on the note #fffbeb 7.10
            requester bubble #174243 on white 11.07   support #174243 on #d3efe3 9.08
            file #017151 on its white pill 6.03, the pill edge #84938f 3.21
            note words #78350f on #fffbeb 8.75   label #fff on #b45309 5.02
            note edge #b45309 on #fffbeb 4.84
     dark   muted #a3b3ae 6.95   error --danger #f87171 5.49   on the note #2b2410 5.57
            requester #e6efed on #26332f 11.23   support #fff on #017151 6.03
            file #5ea99e on its #161f1d pill 6.13, the pill edge #70827d 3.74
            note words #e6efed on #2b2410 13.16   label #1a1a11 on #d08a1e 6.11
            note edge #d08a1e on #2b2410 5.38

   --text-muted is 4.45:1 on --bg-light and --dark-green is 2.52:1 on the dark
   panel (U1 5.3), which is why neither is used for text here. Every line is
   text somebody else typed or a file somebody else named, with no promise of
   a space in it, so overflow-wrap: anywhere is set once on the list. */
.agent-timeline {
  --timeline-muted: #5a6268;
  --timeline-danger: #a71d2a;
  --timeline-file: #017151;
  --timeline-rule: #e6eae8;
  --timeline-edge: #84938f;
  --timeline-theirs: #ffffff;
  --timeline-theirs-edge: #dfe5e2;
  --timeline-ours: #d3efe3;
  --timeline-ours-edge: #b4dfcd;
  --timeline-ours-ink: #174243;
  --note-ground: #fffbeb;
  --note-border: #b45309;
  --note-ink: #78350f;
  --note-label: #b45309;
  --note-on-label: #ffffff;

  overflow-wrap: anywhere;
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.875rem;
}

:root[data-theme='dark'] .agent-timeline {
  --timeline-muted: #a3b3ae;
  --timeline-danger: var(--danger);
  --timeline-file: #5ea99e;
  --timeline-rule: #2b3936;
  --timeline-edge: #70827d;
  --timeline-theirs: #26332f;
  --timeline-theirs-edge: #35443f;
  --timeline-ours: #017151;
  --timeline-ours-edge: #017151;
  --timeline-ours-ink: #ffffff;
  --note-ground: #2b2410;
  --note-border: #d08a1e;
  --note-ink: #e6efed;
  --note-label: #d08a1e;
  --note-on-label: #1a1a11;
}

.agent-timeline__row {
  display: flex;
  color: var(--charcoal);
}

.agent-timeline__row--support {
  justify-content: flex-end;
}

.agent-timeline__message {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  max-width: 84%;
}

.agent-timeline__row--support .agent-timeline__message {
  align-items: flex-end;
}

.agent-timeline__bubble {
  padding: 0.625rem 1rem;
  border: 1px solid var(--timeline-theirs-edge);
  border-radius: 18px;
  border-bottom-left-radius: 6px;
  background: var(--timeline-theirs);
}

.agent-timeline__row--support .agent-timeline__bubble {
  border-color: var(--timeline-ours-edge);
  border-radius: 18px;
  border-bottom-right-radius: 6px;
  background: var(--timeline-ours);
  color: var(--timeline-ours-ink);
}

/* The wall: the whole row is a dashed amber box, the full width of the
   thread, with name, label and time inside it. */
.agent-timeline__row--note {
  padding: 0.75rem 1rem;
  border: 2px dashed var(--note-border);
  border-radius: 12px;
  background: var(--note-ground);
  color: var(--note-ink);
}

.agent-timeline__row--note .agent-timeline__message {
  max-width: none;
  width: 100%;
}

.agent-timeline__row--note .agent-timeline__bubble {
  padding: 0;
  border: none;
  border-radius: 0;
  background: none;
}

.agent-timeline__row--note .agent-timeline__meta,
.agent-timeline__row--note .agent-timeline__author {
  padding: 0;
  color: var(--note-ink);
}

/* Two hairlines run out from a system line to the edges of the thread. */
.agent-timeline__row--system {
  align-items: center;
  gap: 1rem;
}

.agent-timeline__row--system::before,
.agent-timeline__row--system::after {
  content: '';
  flex: 1 1 1.5rem;
  border-top: 1px solid var(--timeline-rule);
}

.agent-timeline__system {
  max-width: 75%;
  margin: 0;
  color: var(--timeline-muted);
  font-size: 0.8rem;
  line-height: 1.5;
  text-align: center;
}

/* inline-block so a line too long for one row moves the whole stamp down
   instead of leaving the zone on a line of its own. */
.agent-timeline__system time {
  display: inline-block;
}

.agent-timeline__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.1rem 0.4rem;
  margin: 0 0 0.25rem;
  padding: 0 0.4rem;
  font-size: 0.78rem;
  color: var(--timeline-muted);
}

.agent-timeline__row--support .agent-timeline__meta {
  justify-content: flex-end;
}

.agent-timeline__author {
  font-weight: 700;
  color: var(--charcoal);
}

.agent-timeline__wall {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.1rem 0.55rem;
  border-radius: 999px;
  background: var(--note-label);
  color: var(--note-on-label);
  font-weight: 700;
  line-height: 1.3;
  white-space: nowrap;
}

.agent-timeline__body {
  margin: 0;
  font-size: 0.94rem;
  line-height: 1.55;
  white-space: pre-wrap;
}

.agent-timeline__files {
  list-style: none;
  margin: 0.375rem 0 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
}

.agent-timeline__row--support .agent-timeline__files {
  justify-content: flex-end;
}

/* A pill under the bubble, still a button that only reads as a file. */
.agent-timeline__file {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  min-height: 2rem;
  padding: 0.3rem 0.875rem 0.3rem 0.72rem;
  border: 1px solid var(--timeline-edge);
  border-radius: 999px;
  background: var(--white);
  color: var(--timeline-file);
  font-family: inherit;
  font-size: 0.85rem;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
}

.agent-timeline__file:hover:not([aria-disabled='true']) {
  text-decoration: underline;
}

.agent-timeline__file[aria-disabled='true'] {
  cursor: progress;
  opacity: 0.6;
}

.agent-timeline__file-error {
  display: block;
  margin-top: 0.15rem;
  color: var(--timeline-danger);
  font-size: 0.8rem;
}
</style>
