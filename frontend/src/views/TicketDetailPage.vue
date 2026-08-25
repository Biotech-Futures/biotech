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
        <TicketStatusBadge :status="ticket.status" />
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
import { onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import TicketReplyBox from '@/components/support/TicketReplyBox.vue'
import TicketStatusBadge from '@/components/support/TicketStatusBadge.vue'
import TicketTimeline from '@/components/support/TicketTimeline.vue'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { formatLongDateAU } from '@/utils/date'
import { categoryLabel, fetchTicket, type TicketDetail } from '@/utils/supportAPI'

const route = useRoute()

const ticket = ref<TicketDetail | null>(null)
const isLoading = ref(true)
const error = ref('')

async function load() {
  isLoading.value = true
  error.value = ''
  try {
    ticket.value = await fetchTicket(String(route.params.id))
  } catch (err) {
    // The backend answers 404 for a ticket that is not yours, exactly as it
    // does for one that does not exist, so there is one message for both.
    error.value = apiErrorFromUnknown(err, 'This enquiry could not be found.').message
  } finally {
    isLoading.value = false
  }
}

// The reply endpoint answers with the whole ticket, so the timeline and the
// status badge both refresh from one response — including a reopen, which
// changes the status without the requester doing anything else.
function onReplied(updated: TicketDetail) {
  ticket.value = updated
}

onMounted(load)
</script>

<style scoped>
.ticket {
  max-width: 60rem;
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
  color: var(--text-muted);
  font-size: 0.85rem;
  font-weight: 600;
  letter-spacing: 0.03em;
}

.ticket__title {
  margin: 0.2rem 0 0.35rem 0;
  font-size: 1.6rem;
}

.ticket__meta {
  margin: 0;
  color: var(--text-muted);
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
  color: var(--text-muted);
}

.ticket__state--error {
  color: var(--danger);
}
</style>
