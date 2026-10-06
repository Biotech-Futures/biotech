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
              class="support__topic-link support__topic-row"
            >
              <span class="support__topic-icon"><TicketIcon :name="topicIcon(topic.title)" /></span>
              <div>
                <h3>{{ topic.title }}</h3>
                <p>{{ topic.blurb }}</p>
                <span class="support__topic-cta">Read the guides &rarr;</span>
              </div>
            </RouterLink>
            <div v-else class="support__topic-row">
              <span class="support__topic-icon"><TicketIcon :name="topicIcon(topic.title)" /></span>
              <div>
                <h3>{{ topic.title }}</h3>
                <p>{{ topic.blurb }}</p>
              </div>
            </div>
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
      <!-- Edge to edge, as the redesign draws it: the head row and the row
           lines run from one side of the card to the other, and the table pads
           its own first and last columns back in line with the title. -->
      <div v-else class="support__table">
        <MyTicketsTable :tickets="tickets" />
      </div>

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
import TicketIcon from '@/components/support/TicketIcon.vue'
import type { TicketIconName } from '@/components/support/ticketIcons'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { SUPPORT_TOPICS, labelIdFor } from '@/utils/supportTopics'
import { fetchMyTickets, type TicketDetail, type TicketRow } from '@/utils/supportAPI'
import { fetchResourceLabels, type ResourceLabel } from '@/utils/resourcesAPI'

// The list itself lives in utils/supportTopics.ts so a test can import the
// same one the page renders. See that file for why the strings are
// load-bearing.
const TOPICS = SUPPORT_TOPICS

// The picture beside each topic. Keyed by title here rather than added to
// SUPPORT_TOPICS, whose strings are matched against resource labels and are
// best left holding only that. A topic added there without an icon here gets
// the plain document one.
const TOPIC_ICONS: Record<string, TicketIconName> = {
  'Account and access': 'key',
  Registration: 'user-plus',
  'Certificates and records': 'award',
}
const topicIcon = (title: string): TicketIconName => TOPIC_ICONS[title] ?? 'file'

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

// Straight to the new ticket: its number, its Open badge and the requester's
// own message are already on the page, so landing there answers "did that
// work?" without a second click. There is no "thanks, we're looking into
// this" line under the message any more (C-05); the page itself is the answer.
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
/* The first redesign round (October 2026) gives the ticket screens their own
   greys, rules and card edge. They are set here, on this page's root, rather
   than in main.css: the global tokens are every other team's too.

   Measured against the grounds they sit on (WCAG AA, 4.5:1 for text):
     light  muted #5a6268  on #ffffff 6.21:1  on the #f8f9fa band 5.89:1
            link  #017151  on #ffffff 6.03:1  icon on its #fcede2 tile 5.27:1
     dark   muted #a3b3ae  on the #1d2826 card 6.95:1  on the #161f1d band 7.71:1
            link  #6dbfb1  on #1d2826 7.04:1  icon on its #143b32 tile 5.72:1
   The dark link is the designer's: brand green on a dark card was 2.52:1. */
.support {
  --ticket-muted: #5a6268;
  --ticket-link: var(--dark-green);
  --ticket-rule: #e6eae8;
  --ticket-card-edge: #e3e7e5;
  --ticket-card-shadow: 0 1px 2px rgba(23, 66, 67, 0.06), 0 4px 12px rgba(23, 66, 67, 0.05);
  --ticket-band: #f8f9fa;
  --ticket-tile: #fcede2;
  --ticket-tile-ink: #017151;
  --ticket-control-edge: #84938f;
}

:root[data-theme='dark'] .support {
  --ticket-muted: #a3b3ae;
  --ticket-link: #6dbfb1;
  --ticket-rule: #2b3936;
  --ticket-card-edge: #2b3936;
  --ticket-card-shadow: 0 1px 3px var(--shadow);
  --ticket-band: #161f1d;
  --ticket-tile: #143b32;
  --ticket-tile-ink: #6dbfb1;
  --ticket-control-edge: #70827d;
}

.support__hero {
  margin-bottom: 1.25rem;
}

.support__eyebrow {
  margin: 0;
  color: var(--ticket-link);
  font-size: 0.8rem;
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.support__title {
  margin: 0.25rem 0 0 0;
  font-size: 2rem;
  line-height: 1.2;
  letter-spacing: -0.01em;
}

.support__subtitle {
  margin: 0;
  color: var(--ticket-muted);
}

/* The narrow column keeps a floor, so a laptop with the sidebar open does not
   squeeze the help topics into a sliver. */
.support__columns {
  display: grid;
  grid-template-columns: minmax(0, 15fr) minmax(17.5rem, 8fr);
  gap: 1.5rem;
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
  border: 1px solid var(--ticket-card-edge);
  border-radius: 12px;
  box-shadow: var(--ticket-card-shadow);
}

.support__selfserve-title {
  margin: 0;
  font-size: 1.15rem;
  line-height: 1.25;
}

.support__selfserve-lede {
  margin: 0.4rem 0 0.5rem 0;
  color: var(--ticket-muted);
  font-size: 0.9rem;
  line-height: 1.5;
}

/* A plain list between rules, one line above the first topic and one below
   the last. */
.support__topics {
  list-style: none;
  margin: 0;
  padding: 0;
  border-top: 1px solid var(--ticket-rule);
  border-bottom: 1px solid var(--ticket-rule);
}

.support__topic {
  padding: 0.95rem 0;
}

.support__topic + .support__topic {
  border-top: 1px solid var(--ticket-rule);
}

.support__topic-row {
  display: flex;
  align-items: flex-start;
  gap: 0.875rem;
}

.support__topic-link {
  color: inherit;
  text-decoration: none;
}

.support__topic-icon {
  display: flex;
  flex: none;
  align-items: center;
  justify-content: center;
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 10px;
  background: var(--ticket-tile);
  color: var(--ticket-tile-ink);
}

.support__topic-cta {
  display: inline-block;
  margin-top: 6px;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--ticket-link);
}

.support__topic-link:hover .support__topic-cta,
.support__topic-link:focus-visible .support__topic-cta {
  text-decoration: underline;
}

.support__topic h3 {
  margin: 0 0 0.2rem 0;
  font-size: 0.95rem;
  font-weight: 700;
  line-height: 1.3;
}

.support__topic p {
  margin: 0;
  color: var(--ticket-muted);
  font-size: 0.85rem;
  line-height: 1.5;
}

.support__resources-link {
  display: inline-block;
  margin-top: 1rem;
  color: var(--ticket-link);
  font-size: 0.9rem;
  font-weight: 600;
  text-decoration: none;
}

.support__resources-link:hover {
  text-decoration: underline;
}

/* No bottom padding: the promise below is a band that runs to the card's
   bottom edge, and overflow keeps its corners inside the card's rounding. */
.support__tickets {
  margin-top: 1.5rem;
  padding: 1.5rem 1.75rem 0;
  overflow: hidden;
  background: var(--surface-elevated);
  border: 1px solid var(--ticket-card-edge);
  border-radius: 12px;
  box-shadow: var(--ticket-card-shadow);
}

.support__tickets-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.support__tickets-title {
  margin: 0;
  font-size: 1.15rem;
  line-height: 1.25;
}

.support__tickets-count {
  margin: 0;
  padding: 0.2rem 0.75rem;
  border: 1px solid var(--ticket-rule);
  border-radius: 999px;
  background: var(--ticket-band);
  color: var(--ticket-muted);
  font-size: 0.78rem;
  font-weight: 700;
  line-height: 1.5;
}

.support__table {
  margin: 0 -1.75rem;
}

.support__promise {
  margin: 1rem -1.75rem 0;
  padding: 0.85rem 1.75rem;
  border-top: 1px solid var(--ticket-rule);
  background: var(--ticket-band);
  color: var(--ticket-muted);
  font-size: 0.85rem;
  line-height: 1.5;
  text-align: center;
}

/* Straight after the table the band sits flush: its top rule is the line
   under the last row, which MyTicketsTable leaves off for that reason. */
.support__table + .support__promise {
  margin-top: 0;
}

.support__state {
  padding: 1.25rem 0;
  color: var(--ticket-muted);
}

.support__state--error {
  color: var(--danger);
}

.support__more {
  margin: 0.9rem 0 1rem;
  text-align: center;
}

.support__more-button {
  padding: 0.5rem 1.1rem;
  border: 1px solid var(--ticket-control-edge);
  border-radius: 8px;
  background: var(--surface-elevated);
  color: var(--charcoal);
  font-size: 0.88rem;
  cursor: pointer;
}

.support__more-button:hover:not(:disabled) {
  border-color: var(--ticket-link);
  color: var(--ticket-link);
}

.support__more-button:disabled {
  cursor: default;
  opacity: 0.6;
}
</style>
