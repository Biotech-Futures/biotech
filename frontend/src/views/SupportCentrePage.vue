<template>
  <div class="content-area support">
    <header class="support__hero">
      <p class="support__eyebrow">Help and support</p>
      <h1 class="support__title">Support Centre</h1>
      <p class="support__subtitle">
        Raise an enquiry with the BIOTech Futures team and follow it through to an answer.
      </p>
    </header>

    <div class="support__columns">
      <TicketForm @submitted="onSubmitted" />

      <aside class="support__selfserve">
        <h2 class="support__selfserve-title">Find help quickly</h2>
        <p class="support__selfserve-lede">
          Browse our most common topics or visit the Resources section for more guides and
          information.
        </p>

        <ul class="support__topics">
          <li v-for="topic in TOPICS" :key="topic.title" class="support__topic">
            <h3>{{ topic.title }}</h3>
            <p>{{ topic.blurb }}</p>
          </li>
        </ul>

        <RouterLink to="/resources" class="support__resources-link">
          View all help articles in Resources &rarr;
        </RouterLink>
      </aside>
    </div>

    <section class="support__tickets">
      <div class="support__tickets-head">
        <h2 class="support__tickets-title">My support tickets</h2>
        <p v-if="!isLoading && total" class="support__tickets-count">
          {{ total }} {{ total === 1 ? 'enquiry' : 'enquiries' }}
        </p>
      </div>

      <p v-if="isLoading" class="support__state">Loading your enquiries&hellip;</p>
      <p v-else-if="error" class="support__state support__state--error" role="alert">{{ error }}</p>
      <MyTicketsTable v-else :tickets="tickets" />

      <div v-if="hasMore && !isLoading" class="support__more">
        <button type="button" class="support__more-button" @click="loadMore">Show more</button>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import MyTicketsTable from '@/components/support/MyTicketsTable.vue'
import TicketForm from '@/components/support/TicketForm.vue'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { fetchMyTickets, type TicketDetail, type TicketRow } from '@/utils/supportAPI'

// The client's three self-serve topics, worded as they wrote them (p48).
const TOPICS = [
  {
    title: 'Account & Access',
    blurb: 'Login issues, password reset, and account settings.'
  },
  {
    title: 'Programs & Groups',
    blurb: 'Course enrolment, group access, and workspace questions.'
  },
  {
    title: 'Certificates & Records',
    blurb: 'Certificate requests, name updates, and transcripts.'
  }
]

const router = useRouter()

const tickets = ref<TicketRow[]>([])
const total = ref(0)
const page = ref(1)
const hasMore = ref(false)
const isLoading = ref(true)
const error = ref('')

async function load(nextPage = 1) {
  isLoading.value = true
  error.value = ''
  try {
    const result = await fetchMyTickets(nextPage)
    tickets.value = nextPage === 1 ? result.items : [...tickets.value, ...result.items]
    total.value = result.total
    page.value = result.page
    hasMore.value = result.hasMore
  } catch (err) {
    error.value = apiErrorFromUnknown(err, 'Could not load your enquiries.').message
  } finally {
    isLoading.value = false
  }
}

function loadMore() {
  load(page.value + 1)
}

// Straight to the new ticket: the acknowledgement is already on its timeline,
// so landing there answers "did that work?" without a second click.
function onSubmitted(ticket: TicketDetail) {
  router.push(`/support/tickets/${ticket.id}`)
}

onMounted(() => load(1))
</script>

<style scoped>
.support__hero {
  margin-bottom: 1.5rem;
}

.support__eyebrow {
  margin: 0;
  color: var(--dark-green);
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.support__title {
  margin: 0.25rem 0 0.4rem 0;
  font-size: 2rem;
}

.support__subtitle {
  margin: 0;
  color: var(--text-muted);
}

.support__columns {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr);
  gap: 1.25rem;
  align-items: start;
}

@media (max-width: 900px) {
  .support__columns {
    grid-template-columns: minmax(0, 1fr);
  }
}

.support__selfserve {
  padding: 1.5rem;
  background: var(--surface-elevated);
  border: 1px solid var(--border-light);
  border-radius: 10px;
  box-shadow: 0 1px 3px var(--shadow);
}

.support__selfserve-title {
  margin: 0;
  font-size: 1.15rem;
}

.support__selfserve-lede {
  margin: 0.4rem 0 1rem 0;
  color: var(--text-muted);
  font-size: 0.88rem;
}

.support__topics {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.support__topic {
  padding: 0.85rem 1rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--bg-light);
}

.support__topic h3 {
  margin: 0 0 0.2rem 0;
  font-size: 0.95rem;
}

.support__topic p {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.85rem;
}

.support__resources-link {
  display: inline-block;
  margin-top: 1rem;
  color: var(--dark-green);
  font-size: 0.9rem;
  font-weight: 600;
  text-decoration: none;
}

.support__resources-link:hover {
  text-decoration: underline;
}

.support__tickets {
  margin-top: 2rem;
  padding: 1.5rem;
  background: var(--surface-elevated);
  border: 1px solid var(--border-light);
  border-radius: 10px;
  box-shadow: 0 1px 3px var(--shadow);
}

.support__tickets-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.75rem;
}

.support__tickets-title {
  margin: 0;
  font-size: 1.15rem;
}

.support__tickets-count {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.85rem;
}

.support__state {
  padding: 1.25rem 0;
  color: var(--text-muted);
}

.support__state--error {
  color: var(--danger);
}

.support__more {
  margin-top: 0.9rem;
  text-align: center;
}

.support__more-button {
  padding: 0.5rem 1.1rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--surface-elevated);
  color: var(--charcoal);
  font-size: 0.88rem;
  cursor: pointer;
}

.support__more-button:hover {
  border-color: var(--dark-green);
  color: var(--dark-green);
}
</style>
