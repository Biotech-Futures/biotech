<template>
  <ol class="timeline">
    <li v-for="message in renderable" :key="message.id" class="timeline__row" :class="rowClass(message)">
      <!-- System notes sit centred and unattributed: they are the ticket
           telling its own story, not somebody speaking. -->
      <p v-if="message.messageType === 'system'" class="timeline__system">
        {{ message.body }}
        <time :datetime="message.createdAt">{{ formatLongDateTimeAU(message.createdAt) }}</time>
      </p>

      <!-- Name and time above the bubble, files hanging under it, all on
           the speaker's side: the messaging-app shape the redesign asks for. -->
      <div v-else class="timeline__message">
        <p class="timeline__meta">
          <span class="timeline__author">{{ message.author || 'You' }}</span>
          <time :datetime="message.createdAt">{{ formatLongDateTimeAU(message.createdAt) }}</time>
        </p>
        <div class="timeline__bubble">
          <p class="timeline__body">{{ message.body }}</p>
        </div>

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
              <TicketIcon name="paperclip" :size="14" />
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
import TicketIcon from '@/components/support/TicketIcon.vue'
import { formatLongDateTimeAU } from '@/utils/date'
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
/* The first redesign round (October 2026): the requester's own messages in a
   mint bubble on the right, support's in a white one on the left, name and
   time above each bubble and files hanging under it, like Messenger. The
   colours are the component's own; --light-green, the old own-bubble ground,
   is the global peach other teams use.

   Everything outside a bubble sits on the page (--bg-light). Measured
   (WCAG AA: 4.5:1 for text, 3:1 for a button's edge):
     light  muted #5a6268 on #f8f9fa 5.89:1
            own bubble #174243 on #d3efe3 9.08:1   support bubble on white 11.07:1
            file #017151 on its white pill 6.03:1, the pill edge #84938f 3.04:1
     dark   muted #a3b3ae on #0f1715 8.34:1
            own bubble #ffffff on #017151 6.03:1   support #e6efed on #26332f 11.23:1
            file #6dbfb1 on its #161f1d pill 7.80:1, the pill edge #70827d 4.49:1
   The dark values are the designer's (his dark pending-user page); the pill
   in dark is ours, in his dark colours, since he drew it only in light. */
/* Every line on this timeline is text somebody else typed or a file
   somebody else named, and none of it is guaranteed to have a space in it:
   a bounce note carries an email address, an attachment carries a filename,
   a bubble carries a pasted link. One unbroken run sets the minimum width of
   the whole .content-area, so the page scrolls sideways rather than the text
   wrapping. Declared once here so it reaches all four. `anywhere` rather
   than `break-word` because only `anywhere` lowers the min-content width,
   which is the number that gets used. */
.timeline {
  --ticket-muted: #5a6268;
  --ticket-danger: #a71d2a;
  --timeline-rule: #e6eae8;
  --timeline-mine: #d3efe3;
  --timeline-mine-edge: #b4dfcd;
  --timeline-mine-ink: #174243;
  --timeline-theirs: #ffffff;
  --timeline-theirs-edge: #dfe5e2;
  --timeline-file: var(--dark-green);
  --timeline-file-edge: #84938f;

  overflow-wrap: anywhere;
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  /* From the foot of one message to the name over the next. */
  gap: 0.875rem;
}

:root[data-theme="dark"] .timeline {
  --ticket-muted: #a3b3ae;
  --ticket-danger: var(--danger);
  --timeline-rule: #2b3936;
  --timeline-mine: #017151;
  --timeline-mine-edge: #017151;
  --timeline-mine-ink: #ffffff;
  --timeline-theirs: #26332f;
  --timeline-theirs-edge: #35443f;
  --timeline-file: #6dbfb1;
  --timeline-file-edge: #70827d;
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

/* Shaped after the messaging apps students already use; Instagram and
   Messenger were the references for client item C-07. A message may fill 74%
   of the thread, which runs the full width of the page: that is the
   designer's layout, and it was chosen over keeping the thread narrow
   (decision DEC-046). The corner nearest the speaker is tucked in so each
   side still says whose it is at a glance. */
.timeline__message {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  max-width: 74%;
}

.timeline__row--mine .timeline__message {
  align-items: flex-end;
}

.timeline__bubble {
  padding: 0.625rem 1rem;
  border-radius: 18px;
  border: 1px solid var(--timeline-theirs-edge);
  background: var(--timeline-theirs);
}

.timeline__row--mine .timeline__bubble {
  background: var(--timeline-mine);
  border-color: var(--timeline-mine-edge);
  border-bottom-right-radius: 6px;
  color: var(--timeline-mine-ink);
}

.timeline__row--support .timeline__bubble {
  border-bottom-left-radius: 6px;
}

/* Wraps whole pieces onto a second line. With the time in it the stamp is
   long enough that a name and a stamp outgrow the space on a phone, and
   without wrap the two squeeze side by side and the date splits across
   lines. Set in from the bubble's edge a little, on the speaker's side. */
.timeline__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.1rem 0.4rem;
  align-items: baseline;
  margin: 0 0 0.25rem 0;
  padding: 0 0.4rem;
  font-size: 0.78rem;
  color: var(--ticket-muted);
}

.timeline__row--mine .timeline__meta {
  justify-content: flex-end;
}

.timeline__author {
  font-weight: 700;
  color: var(--charcoal);
}

.timeline__body {
  margin: 0;
  font-size: 0.94rem;
  line-height: 1.55;
  /* Line breaks the requester typed are part of what they wrote. */
  white-space: pre-wrap;
  word-break: break-word;
}

/* A line of small text between two hairlines that run out to the edges of
   the thread. The hairlines are the row's own, so the note itself stays one
   block of text and its stamp can still drop to a second line whole. */
.timeline__row--system {
  align-items: center;
  gap: 1rem;
}

.timeline__row--system::before,
.timeline__row--system::after {
  content: '';
  flex: 1 1 1.5rem;
  border-top: 1px solid var(--timeline-rule);
}

.timeline__system {
  max-width: 75%;
  margin: 0;
  color: var(--ticket-muted);
  font-size: 0.8rem;
  line-height: 1.5;
  text-align: center;
}

/* No opacity on the date. Fading muted text by a quarter puts whatever it is
   sitting on back into the mix: 0.75 took this from 5.29:1 down to 3.19:1,
   which undid the colour above. The space already separates it.
   inline-block so that a note too long for one line moves the whole stamp to
   the next line instead of leaving "24" at the end of one and "September
   2026, 3:37 pm" on the next. Not nowrap: on a screen narrower than the stamp
   it can still wrap inside itself rather than push the page sideways. */
.timeline__system time {
  display: inline-block;
  margin-left: 0.25rem;
}

.timeline__files {
  list-style: none;
  margin: 0.375rem 0 0 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-start;
  gap: 0.375rem;
}

.timeline__row--mine .timeline__files {
  justify-content: flex-end;
}

/* A pill under the bubble. Still a button that only reads as a file. */
.timeline__file {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  min-height: 2rem;
  padding: 0.3rem 0.875rem 0.3rem 0.72rem;
  border: 1px solid var(--timeline-file-edge);
  border-radius: 999px;
  background: var(--white);
  color: var(--timeline-file);
  font-family: inherit;
  font-size: 0.85rem;
  font-weight: 600;
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
