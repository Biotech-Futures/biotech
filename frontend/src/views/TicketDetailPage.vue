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
        We are waiting on you. Reply below and we will pick this straight back up.
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
/* Muted text and the error line both take a literal colour rather than
   --text-muted and --danger. On this page the ground is .content-area's
   --bg-light, where those two tokens are 4.45:1 and 4.30:1, both under AA.
   The values here are the ones TicketPriorityBadge.vue measured. Dark hands
   both back to the theme, which is comfortable there. */
.ticket {
  --ticket-muted: #616970;
  --ticket-danger: #a71d2a;

  max-width: 60rem;
}

:root[data-theme="dark"] .ticket {
  --ticket-muted: var(--text-muted);
  --ticket-danger: var(--danger);
}

.ticket__back {
  display: inline-block;
  margin-bottom: 1rem;
  color: var(--dark-green);
  font-size: 0.88rem;
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
  border-bottom: 1px solid var(--border-light);
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
  margin: 0.2rem 0 0.35rem 0;
  font-size: 1.6rem;
  overflow-wrap: anywhere;
}

.ticket__badges {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.35rem;
}

.ticket__meta {
  margin: 0;
  color: var(--ticket-muted);
  font-size: 0.85rem;
}

.ticket__callout {
  margin: 1rem 0 0 0;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  background: rgba(255, 193, 7, 0.14);
  color: #8a6100;
  font-size: 0.9rem;
}

.ticket__conversation {
  margin: 1.5rem 0;
}

.ticket__state {
  padding: 2rem 0;
  color: var(--ticket-muted);
}

.ticket__state--error {
  color: var(--ticket-danger);
}
</style>
