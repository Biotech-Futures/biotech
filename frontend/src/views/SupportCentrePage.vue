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
            <!-- A link only once the library actually has that shelf. A topic
                 with no matching label stays as plain text rather than
                 becoming a link to an empty list. -->
            <RouterLink
              v-if="topicLabelId(topic.title)"
              :to="{ path: '/resources', query: { label: topicLabelId(topic.title) } }"
              class="support__topic-link"
            >
              <h3>{{ topic.title }}</h3>
              <p>{{ topic.blurb }}</p>
              <span class="support__topic-cta">Read the guides &rarr;</span>
            </RouterLink>
            <template v-else>
              <h3>{{ topic.title }}</h3>
              <p>{{ topic.blurb }}</p>
            </template>
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

      <!-- The rows already on screen stay put while the next page loads, and
           stay put if it fails. Reusing the page-level state here made
           "Show more" blank the list before adding to it. -->
      <p v-if="moreError" class="support__state support__state--error" role="alert">
        {{ moreError }}
      </p>

      <div v-if="hasMore && !isLoading" class="support__more">
        <button
          type="button"
          class="support__more-button"
          :disabled="isLoadingMore"
          @click="loadMore"
        >
          {{ isLoadingMore ? 'Loading…' : 'Show more' }}
        </button>
      </div>

      <!-- p48 closes with "You can reply to any open ticket in this portal or
           by email. We'll keep all updates in one place." Only the first half
           is true today: replies by email are a later goal and nothing reads
           that mailbox yet, so promising it here would send students to write
           into a void. The half we do deliver is stated instead — every
           update really does reach them by email. Restore the client's exact
           sentence when inbound email lands. -->
      <p class="support__promise">
        You can reply to any open enquiry on this page, and we will email you
        every update. We keep the whole conversation in one place.
      </p>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import MyTicketsTable from '@/components/support/MyTicketsTable.vue'
import TicketForm from '@/components/support/TicketForm.vue'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { SUPPORT_TOPICS, labelIdFor } from '@/utils/supportTopics'
import { fetchMyTickets, type TicketDetail, type TicketRow } from '@/utils/supportAPI'
import { fetchResourceLabels, type ResourceLabel } from '@/utils/resourcesAPI'

// The list itself lives in utils/supportTopics.ts so a test can import the
// same one the page renders. See that file for why the strings are
// load-bearing.
const TOPICS = SUPPORT_TOPICS

// The knowledge base is the resource library, not a second store of articles:
// the platform already has rich-text resources, an editor the client can use,
// and role-based visibility. So "knowledge base" is a naming convention — a
// resource label whose name matches the topic — and the client adds an
// article by writing a resource and labelling it. Nothing here needs to
// change when they do.
const labels = ref<ResourceLabel[]>([])

// Imported rather than written here: a <script setup> binding cannot be
// imported, so the test that covered this had a copy of the function in the
// test file and pinned the rule instead of the implementation.
const topicLabelId = (topic: string) => labelIdFor(topic, labels.value)

const router = useRouter()

const tickets = ref<TicketRow[]>([])
const total = ref(0)
const page = ref(1)
const hasMore = ref(false)
const isLoading = ref(true)
const isLoadingMore = ref(false)
const error = ref('')
const moreError = ref('')
// Where this run of "Show more" has got to: the snapshot it is walking plus
// the place the last page ended. The first page sends neither — loading it is
// how someone asks for what is there now — and every page after sends both.
const walk = ref<{ asOf: string; after: string } | undefined>(undefined)

// The first page owns the page-level loading and error state, because there is
// nothing on screen yet to protect. Later pages get their own, so a failure
// adds a line under the table instead of replacing the table with it.
async function load(nextPage = 1) {
  const isFirstPage = nextPage === 1
  if (isFirstPage) {
    isLoading.value = true
    error.value = ''
  } else {
    isLoadingMore.value = true
    moreError.value = ''
  }
  try {
    const result = await fetchMyTickets(nextPage, 10, isFirstPage ? undefined : walk.value)
    // Each page hands the next one its starting place. A null cursor means
    // there was no last row, which only happens on an empty page.
    walk.value = result.after ? { asOf: result.asOf, after: result.after } : undefined
    tickets.value = isFirstPage ? result.items : [...tickets.value, ...result.items]
    total.value = result.total
    page.value = result.page
    hasMore.value = result.hasMore
  } catch (err) {
    const message = apiErrorFromUnknown(err, 'Could not load your enquiries.').message
    if (isFirstPage) {
      error.value = message
    } else {
      moreError.value = message
    }
  } finally {
    isLoading.value = false
    isLoadingMore.value = false
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

onMounted(() => {
  load(1)
  // Deliberately not awaited and deliberately swallowed: the topic cards are
  // a nice-to-have, and a failure here must not stop somebody raising a
  // ticket. Without the labels they simply render as plain text.
  fetchResourceLabels()
    .then((rows) => {
      labels.value = rows
    })
    .catch(() => {
      labels.value = []
    })
})
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

.support__topic-link {
  display: block;
  color: inherit;
  text-decoration: none;
}

.support__topic-cta {
  display: inline-block;
  margin-top: 6px;
  font-size: 0.85rem;
  font-weight: 600;
  color: #307054;
}

.support__topic-link:hover .support__topic-cta,
.support__topic-link:focus-visible .support__topic-cta {
  text-decoration: underline;
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

.support__promise {
  margin: 1rem 0 0;
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

.support__more-button:hover:not(:disabled) {
  border-color: var(--dark-green);
  color: var(--dark-green);
}

.support__more-button:disabled {
  cursor: default;
  opacity: 0.6;
}
</style>
