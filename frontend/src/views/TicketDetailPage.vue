<template>
  <div class="content-area ticket">
    <RouterLink to="/support" class="ticket__back">&larr; Back to Support Centre</RouterLink>

    <p v-if="isLoading" class="ticket__state">Loading this enquiry&hellip;</p>
    <p v-else-if="error" class="ticket__state ticket__state--error" role="alert">{{ error }}</p>

    <template v-else-if="ticket">
      <header class="ticket__head">
        <div>
          <p class="ticket__number">#{{ ticket.ticketNumber }}</p>
          <h1 class="ticket__title">{{ ticket.subject }}</h1>
          <p class="ticket__meta">
            {{ categoryLabel(ticket.category) }}
            &middot; Raised {{ formatLongDateAU(ticket.createdAt) }}
            &middot; Last updated {{ formatLongDateAU(ticket.lastUpdated) }}
          </p>
        </div>
        <div class="ticket__badges">
          <TicketStatusBadge :status="ticket.status" />
          <TicketPriorityBadge :priority="ticket.priority" />
        </div>
      </header>

      <p v-if="ticket.status === 'pending_user'" class="ticket__callout">
        <TicketIcon name="reply" class="ticket__callout-icon" />
        <span>We are waiting on you. Reply below and we will pick this straight back up.</span>
      </p>

      <section class="ticket__conversation">
        <TicketTimeline :ticket-id="ticket.id" :messages="ticket.messages" />
      </section>

      <TicketReplyBox
        :ticket-id="ticket.id"
        :is-resolved="ticket.status === 'resolved'"
        @replied="onReplied"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import TicketIcon from '@/components/support/TicketIcon.vue'
import TicketReplyBox from '@/components/support/TicketReplyBox.vue'
import TicketStatusBadge from '@/components/support/TicketStatusBadge.vue'
import TicketPriorityBadge from '@/components/support/TicketPriorityBadge.vue'
import TicketTimeline from '@/components/support/TicketTimeline.vue'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { formatLongDateAU } from '@/utils/date'
import { categoryLabel, fetchTicket, type TicketDetail } from '@/utils/supportAPI'

const route = useRoute()

const ticket = ref<TicketDetail | null>(null)
const isLoading = ref(true)
const error = ref('')

// Which load is the current one. Changing the address bar twice in a row
// leaves two requests in flight, and the slower one must not paint over the
// newer one: that would put a ticket on screen that the URL is not asking for,
// which is the whole thing this page has to get right.
let loadToken = 0

async function load() {
  const token = ++loadToken
  isLoading.value = true
  error.value = ''
  try {
    const loaded = await fetchTicket(String(route.params.id))
    if (token !== loadToken) return
    ticket.value = loaded
  } catch (err) {
    if (token !== loadToken) return
    // A 404 arrives carrying its own sentence, and the backend answers 404
    // for a ticket that is not yours exactly as it does for one that does
    // not exist, so both land on that one sentence without help from here.
    // What reaches the fallback is the request that never came back at all:
    // a dropped connection, a cancelled request, an answer that is not JSON.
    // So the fallback must not say the enquiry is missing. It used to, and a
    // student on a train was told their ticket did not exist.
    error.value = apiErrorFromUnknown(
      err,
      'We could not load this enquiry. Check your connection and try again.'
    ).message
  } finally {
    if (token === loadToken) isLoading.value = false
  }
}

// The reply endpoint answers with the whole ticket, so the timeline and the
// status badge both refresh from one response — including a reopen, which
// changes the status without the requester doing anything else.
function onReplied(updated: TicketDetail) {
  ticket.value = updated
}

onMounted(load)

// The id in the address can change without this component being torn down: a
// typed URL, a bookmark, the back and forward buttons. Without this the page
// keeps the ticket it first loaded while the address bar names another one,
// and the reply box underneath is still bound to the old ticket's id. Every
// other detail view in the portal watches its route param; this one did not.
watch(() => route.params.id, load)
</script>

<style scoped>
/* Muted text and the error line take literal colours rather than
   --text-muted and --danger. On this page the ground is .content-area's
   --bg-light, where those two tokens are 4.45:1 and 4.30:1, both under AA.
   The muted grey is the first redesign round's (October 2026), on every
   ticket screen. Measured on the page:
     light  muted #5a6268 on #f8f9fa 5.89:1   danger #a71d2a 6.98:1
            waiting note #7a5600 on #fff4d2 6.05:1
     dark   muted #a3b3ae on #0f1715 8.34:1   back link #6dbfb1 8.44:1
            waiting note #fbbf24 on #3f3a17 6.88:1
   Dark hands the danger colour back to the theme, which is comfortable
   there. The dark back link is the designer's: brand green on the dark page
   was 3.02:1. */
.ticket {
  --ticket-muted: #5a6268;
  --ticket-danger: #a71d2a;
  --ticket-link: var(--dark-green);
  --ticket-rule: #e6eae8;
  --ticket-wait: #fff4d2;
  --ticket-wait-ink: #7a5600;
  --ticket-wait-edge: #e0b252;

  max-width: 60rem;
}

:root[data-theme="dark"] .ticket {
  --ticket-muted: #a3b3ae;
  --ticket-danger: var(--danger);
  --ticket-link: #6dbfb1;
  --ticket-rule: #2b3936;
  --ticket-wait: #3f3a17;
  --ticket-wait-ink: #fbbf24;
  --ticket-wait-edge: #fbbf24;
}

/* A block as wide as its words, so the negative margin moves it: an inline
   box cannot rise above the line it sits in. */
.ticket__back {
  display: block;
  width: fit-content;
  margin: -0.4rem 0 0.75rem 0;
  color: var(--ticket-link);
  font-size: 0.9rem;
  font-weight: 600;
  text-decoration: none;
}

.ticket__back:hover {
  text-decoration: underline;
}

.ticket__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--ticket-rule);
}

.ticket__number {
  margin: 0;
  color: var(--ticket-muted);
  font-size: 0.85rem;
  font-weight: 600;
  letter-spacing: 0.03em;
}

/* Same reason as the subject column in MyTicketsTable.vue: a subject is
   whatever the requester typed, and people paste links into them. One
   unbroken 200-character URL here sets the minimum width of the whole
   .content-area, so the page itself starts scrolling sideways at every
   viewport. `anywhere` rather than `break-word` because only `anywhere`
   lowers the min-content width, which is the number that gets used. */
.ticket__title {
  margin: 0.15rem 0 0.25rem 0;
  font-size: 1.6rem;
  line-height: 1.4;
  letter-spacing: -0.01em;
  overflow-wrap: anywhere;
}

/* Status and priority are two separate facts about the enquiry. At 0.35rem
   apart the client read them as too close to each other (client item C-08). */
.ticket__badges {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.6rem;
}

.ticket__meta {
  margin: 0;
  color: var(--ticket-muted);
  font-size: 0.85rem;
}

/* The one thing a requester has to act on, so it is drawn to be seen: a bar
   down the left, a reply arrow and bold text, in the pending user amber. */
.ticket__callout {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  margin: 1.5rem 0 0 0;
  padding: 0.7rem 1rem 0.7rem 1.25rem;
  border-left: 4px solid var(--ticket-wait-edge);
  border-radius: 8px;
  background: var(--ticket-wait);
  color: var(--ticket-wait-ink);
  font-size: 0.95rem;
  font-weight: 700;
  line-height: 1.5;
}

/* Level with the first line of text when the sentence wraps. */
.ticket__callout-icon {
  margin-top: 0.15rem;
}

/* The thread runs the full width of the page, the designer's layout for it
   (decision DEC-046). TicketTimeline.vue sizes its messages as a share of
   this width. */
.ticket__conversation {
  margin: 1.25rem 0 1.5rem;
}

.ticket__state {
  padding: 2rem 0;
  color: var(--ticket-muted);
}

.ticket__state--error {
  color: var(--ticket-danger);
}
</style>
