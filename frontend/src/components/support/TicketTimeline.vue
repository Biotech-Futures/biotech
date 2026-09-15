<template>
  <ol class="timeline">
    <li v-for="message in renderable" :key="message.id" class="timeline__row" :class="rowClass(message)">
      <!-- System notes sit centred and unattributed: they are the ticket
           telling its own story, not somebody speaking. -->
      <p v-if="message.messageType === 'system'" class="timeline__system">
        {{ message.body }}
        <time :datetime="message.createdAt">{{ formatLongDateAU(message.createdAt) }}</time>
      </p>

      <div v-else class="timeline__bubble">
        <p class="timeline__meta">
          <span class="timeline__author">{{ message.author || 'You' }}</span>
          <time :datetime="message.createdAt">{{ formatLongDateAU(message.createdAt) }}</time>
        </p>
        <p class="timeline__body">{{ message.body }}</p>

        <!-- A button, not a link, and not for styling reasons.
             This was an anchor pointing straight at the download endpoint, and
             two things were wrong with that which pull in opposite directions,
             so neither could be fixed on its own. With target="_blank" a tab
             is opened per click and none are closed: three clicks, four tabs.
             Re-measured 2026-09-14 on the merged tree with the target put
             back, headless, via Playwright: WebKit 26.4 and Chromium
             148.0.7778.96 both went 1 -> 2 -> 3 -> 4. An older note here said
             Chromium closed them and that this was why the leak looked fine;
             that does not reproduce and has been removed rather than repeated.
             Without the target, a click is a top-level navigation the browser
             commits to before it knows what
             is coming back — so the moment the endpoint refuses, its error
             page replaces this whole page and takes the half-typed reply
             underneath with it. An agent deleting the ticket as a duplicate is
             enough to cause that.
             A button runs downloadTicketAttachment instead: it fetches, so a
             refusal is a value rendered right here, and it never navigates, so
             there is nothing for WebKit to leave lying around. A `download`
             attribute on the old anchor would not have helped either — the
             file comes from the API origin and the attribute is ignored
             cross-origin. The blob: URL the helper builds is same-origin, so
             there it works. -->
        <ul v-if="message.attachments.length" class="timeline__files">
          <li v-for="file in message.attachments" :key="file.id">
            <button
              type="button"
              class="timeline__file"
              :disabled="busy[file.id]"
              @click="download(file)"
            >
              <i class="fas fa-paperclip"></i>
              {{ file.filename }}
            </button>
            <span v-if="failed[file.id]" class="timeline__file-error" role="alert">{{
              failed[file.id]
            }}</span>
          </li>
        </ul>
      </div>
    </li>
  </ol>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { formatLongDateAU } from '@/utils/date'
import {
  attachmentErrorMessage,
  downloadTicketAttachment,
  type TicketAttachment,
  type TicketMessage
} from '@/utils/supportAPI'

const props = defineProps<{ ticketId: number | string; messages: TicketMessage[] }>()

// Which files are in flight, and what went wrong with which one. Both are
// keyed by attachment id rather than held as one value: five files fit on a
// message, they are five separate answers, and a failure on one must not label
// another. Per-file rather than one global "busy" flag for the same reason —
// a single flag makes a click on the second file do nothing at all while the
// first is still downloading, which is a link behaviour this must not lose.
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
  failed.value = without(failed.value, file.id)
  try {
    await downloadTicketAttachment(props.ticketId, file.id, file.filename)
  } catch (err) {
    // Deliberately not a redirect to the login page on a 401 or 403. Sending
    // them anywhere is the thing this component exists to stop: whatever is in
    // the reply box is still there, and it is theirs.
    failed.value = { ...failed.value, [file.id]: attachmentErrorMessage(err) }
  } finally {
    busy.value = without(busy.value, file.id)
  }
}

// Only the three types this side of the wall knows about. Internal notes are
// already stripped by the backend's queryset — that is where the rule is
// enforced, not here — but rendering nothing for a type we do not recognise
// keeps a future backend change from surfacing something by accident.
const RENDERABLE = ['user_message', 'support_reply', 'system']

const renderable = computed(() =>
  props.messages.filter((message) => RENDERABLE.includes(message.messageType))
)

function rowClass(message: TicketMessage) {
  return {
    'timeline__row--mine': message.messageType === 'user_message',
    'timeline__row--support': message.messageType === 'support_reply',
    'timeline__row--system': message.messageType === 'system'
  }
}
</script>

<style scoped>
/* --text-muted is 4.45:1 on the system note's --bg-light and 4.10:1 on the
   requester's own --light-green bubble, both under AA. The literal is the
   value TicketPriorityBadge.vue measured; dark hands it back to the theme,
   which is 5.37:1 on that same bubble. */
/* Every line on this timeline is text somebody else typed or a file
   somebody else named, and none of it is guaranteed to have a space in it:
   a bounce note carries an email address, an attachment carries a filename,
   a bubble carries a pasted link. One unbroken run sets the minimum width of
   the whole .content-area, so the page scrolls sideways rather than the text
   wrapping. Declared once here so it reaches all four. `anywhere` rather
   than `break-word` because only `anywhere` lowers the min-content width,
   which is the number that gets used. */
.timeline {
  --ticket-muted: #616970;
  --ticket-danger: #a71d2a;

  overflow-wrap: anywhere;
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

:root[data-theme="dark"] .timeline {
  --ticket-muted: var(--text-muted);
  --ticket-danger: var(--danger);
}

.timeline__row {
  display: flex;
}

.timeline__row--mine {
  justify-content: flex-end;
}

.timeline__row--support {
  justify-content: flex-start;
}

.timeline__row--system {
  justify-content: center;
}

.timeline__bubble {
  max-width: min(38rem, 82%);
  padding: 0.75rem 1rem;
  border-radius: 10px;
  border: 1px solid var(--border-light);
  background: var(--surface-elevated);
}

.timeline__row--mine .timeline__bubble {
  background: var(--light-green);
  border-color: transparent;
}

.timeline__meta {
  display: flex;
  gap: 0.6rem;
  align-items: baseline;
  margin: 0 0 0.3rem 0;
  font-size: 0.78rem;
  color: var(--ticket-muted);
}

.timeline__author {
  font-weight: 700;
  color: var(--charcoal);
}

.timeline__body {
  margin: 0;
  font-size: 0.94rem;
  line-height: 1.6;
  /* Line breaks the requester typed are part of what they wrote. */
  white-space: pre-wrap;
  word-break: break-word;
}

.timeline__system {
  margin: 0;
  padding: 0.45rem 0.9rem;
  border-radius: 999px;
  background: var(--bg-light);
  color: var(--ticket-muted);
  font-size: 0.83rem;
  text-align: center;
}

/* No opacity on the date. Fading muted text by a quarter puts whatever it is
   sitting on back into the mix: 0.75 took this from 5.29:1 down to 3.19:1,
   which undid the colour above. The space already separates it. */
.timeline__system time {
  margin-left: 0.5rem;
}

.timeline__files {
  list-style: none;
  margin: 0.55rem 0 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

/* Reads as the link it replaced: same colour, same size, underline on hover. */
.timeline__file {
  padding: 0;
  border: none;
  background: none;
  color: var(--dark-green);
  font-family: inherit;
  font-size: 0.85rem;
  text-align: left;
  text-decoration: none;
  cursor: pointer;
}

.timeline__file:hover:not(:disabled) {
  text-decoration: underline;
}

.timeline__file:disabled {
  cursor: progress;
  opacity: 0.6;
}

/* --ticket-danger is declared on .timeline above for the same reason
   --ticket-muted is: --danger is 4.30:1 on --bg-light, under AA. Dark hands it
   back to the theme, which is comfortable there. Same shape as
   TicketDetailPage.vue, and ticketMutedContrast.spec.ts measures both. */
.timeline__file-error {
  display: block;
  margin-top: 0.15rem;
  color: var(--ticket-danger);
  font-size: 0.8rem;
}
</style>
