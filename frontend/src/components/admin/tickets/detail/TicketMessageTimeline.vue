<template>
  <ol class="agent-timeline" aria-label="Conversation">
    <li
      v-for="message in messages"
      :key="message.id"
      class="agent-timeline__row"
      :class="{
        'agent-timeline__row--system': message.messageType === 'system',
        'agent-timeline__row--note': message.messageType === 'internal_note'
      }"
    >
      <!-- System lines sit centred and unattributed: the ticket telling its
           own story, not somebody speaking. The sentences are fixed on the
           server (services/system_messages.py). -->
      <p v-if="message.messageType === 'system'" class="agent-timeline__system">
        {{ message.body }} ·
        <time :datetime="message.createdAt">{{ when(message.createdAt) }}</time>
      </p>

      <template v-else>
        <p class="agent-timeline__meta">
          <span class="agent-timeline__author">{{ authorLabel(message) }}</span>
          <!-- The wall made visible: the same amber and lock the note box
               below uses, so a note already sent reads as one. The lock is
               hidden from screen readers, which hear "Internal note". -->
          <span v-if="message.messageType === 'internal_note'" class="agent-timeline__wall">
            <span aria-hidden="true">🔒</span> Internal note
          </span>
          <time class="agent-timeline__time" :datetime="message.createdAt">{{
            when(message.createdAt)
          }}</time>
        </p>
        <!-- Plain text, never v-html. Line breaks are part of what was typed. -->
        <p class="agent-timeline__body">{{ message.body }}</p>

        <ul v-if="message.attachments.length" class="agent-timeline__files">
          <li v-for="file in message.attachments" :key="file.id">
            <!-- A button, not a link. An anchor at the download endpoint is a
                 navigation the browser commits to before it knows the answer,
                 so a refusal replaces this app with DRF's error page and takes
                 the half-typed reply with it; with target="_blank" WebKit
                 leaks an empty tab per click instead. See
                 downloadTicketAttachment in utils/ticketAgentAPI.ts. -->
            <button
              type="button"
              class="agent-timeline__file"
              :disabled="busy[file.id]"
              @click="download(file)"
            >
              <i class="fas fa-paperclip" aria-hidden="true"></i>
              {{ file.filename }}
            </button>
            <span v-if="failed[file.id]" class="agent-timeline__file-error" role="alert">{{
              failed[file.id]
            }}</span>
          </li>
        </ul>
      </template>
    </li>
  </ol>
</template>

<script setup lang="ts">
import { ref } from 'vue'

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
    // In finally, or one click leaves the button disabled for good.
    busy.value = without(busy.value, file.id)
  }
}
</script>

<style scoped>
/* Colours are literals where the token fails AA on this ground, measured with
   the WCAG formula (contrast.mjs in the port notes):

     light  muted #616970 on #ffffff 5.58   on the note's #fffbeb 5.38
            error #a71d2a on #ffffff 7.36   on #fffbeb 7.10
            file  #017151 on #ffffff 6.03   on #fffbeb 5.82
            wall  #78350f on #fffbeb 8.75   border #d97706 on #fffbeb 3.07
     dark   muted --text-muted #8a9a96 on --white #161f1d 5.72  on #2b2410 5.24
            error --danger #f87171 on #161f1d 6.08  on #2b2410 5.57
            file  #5ea99e on #161f1d 6.13   on #2b2410 5.61
            wall  #fbbf24 on #2b2410 9.23   border #b45309 on #2b2410 3.07

   --text-muted is 4.45:1 on --bg-light and --dark-green is 2.79:1 on the dark
   surface (U1 5.3), which is why neither is used for text here. Every line is
   text somebody else typed or a file somebody else named, with no promise of
   a space in it, so overflow-wrap: anywhere is set once on the list. */
.agent-timeline {
  --timeline-muted: #616970;
  --timeline-danger: #a71d2a;
  --timeline-file: #017151;
  --note-ground: #fffbeb;
  --note-border: #d97706;
  --note-ink: #78350f;

  overflow-wrap: anywhere;
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

:root[data-theme='dark'] .agent-timeline {
  --timeline-muted: var(--text-muted);
  --timeline-danger: var(--danger);
  --timeline-file: #5ea99e;
  --note-ground: #2b2410;
  --note-border: #b45309;
  --note-ink: #fbbf24;
}

.agent-timeline__row {
  padding: 0.75rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--white);
  color: var(--charcoal);
}

.agent-timeline__row--system {
  padding: 0.25rem 0;
  border: none;
  background: transparent;
}

/* Dashed amber on amber: the wall. */
.agent-timeline__row--note {
  border: 2px dashed var(--note-border);
  background: var(--note-ground);
}

.agent-timeline__system {
  margin: 0;
  color: var(--timeline-muted);
  font-size: 0.78rem;
  text-align: center;
}

.agent-timeline__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.1rem 0.6rem;
  margin: 0 0 0.3rem;
  font-size: 0.78rem;
  color: var(--timeline-muted);
}

.agent-timeline__author {
  font-weight: 700;
  color: var(--charcoal);
}

.agent-timeline__wall {
  font-weight: 700;
  color: var(--note-ink);
}

.agent-timeline__body {
  margin: 0;
  font-size: 0.92rem;
  line-height: 1.55;
  white-space: pre-wrap;
}

.agent-timeline__files {
  list-style: none;
  margin: 0.5rem 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

/* Reads as the link it replaced. */
.agent-timeline__file {
  display: inline-flex;
  align-items: baseline;
  gap: 0.35rem;
  padding: 0;
  border: none;
  background: none;
  color: var(--timeline-file);
  font-family: inherit;
  font-size: 0.82rem;
  text-align: left;
  text-decoration: underline;
  cursor: pointer;
}

.agent-timeline__file:disabled {
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
