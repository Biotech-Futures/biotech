<template>
  <div class="queue-table">
    <p v-if="loading" class="queue-table__state" role="status">Loading the queue…</p>

    <!-- Never the empty state: "no tickets match these filters" is a claim
         about the queue, and a request that failed licenses no claim about
         it. Guarded on having nothing to show, because the queue refetches
         when the tab becomes visible again. One failed background refresh
         must not replace a screen of real tickets with a single line of red
         text; the page-level banner already says the data may be stale. -->
    <p
      v-else-if="failed && !tickets.length"
      class="queue-table__state queue-table__state--error"
      role="alert"
    >
      The queue could not be loaded.
    </p>

    <!-- Same rule as the failed request above: "no tickets match these
         filters" is a claim about the queue, and past page one this page
         cannot make it. A walk is frozen at the moment it started, so every
         ticket somebody works leaves the set the walk is reading. When the
         rows in front of the reader are all worked, the next page arrives
         empty while the tickets on it still match perfectly well. -->
    <p v-else-if="!tickets.length" class="queue-table__state">
      {{
        continuesWalk
          ? 'Nothing left on this page. The tickets that were here have been worked on since you opened the queue, which moves them to the front of it. Go back to page 1 to see them.'
          : 'No tickets match these filters.'
      }}
    </p>

    <div v-else class="queue-table__scroll">
      <table class="queue-table__table">
        <caption class="sr-only">Tickets, most recently active first</caption>
        <thead>
          <tr>
            <th scope="col" class="queue-table__check">
              <input
                type="checkbox"
                :checked="allOnPage"
                :indeterminate.prop="someOnPage && !allOnPage"
                aria-label="Select every ticket on this page"
                @change="emit('toggle-all')"
              />
            </th>
            <th scope="col">Ticket</th>
            <th scope="col">Requester</th>
            <th scope="col">Subject</th>
            <th scope="col">Status</th>
            <th scope="col">Priority</th>
            <th scope="col">Assignee</th>
            <th scope="col">Last activity</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="ticket in tickets"
            :key="ticket.id"
            class="queue-table__row"
            :class="{ 'queue-table__row--selected': selectedSet.has(ticket.id) }"
            @click="openFromRow($event, ticket.id)"
          >
            <!-- Stops the click reaching the row: ticking a box must not also
                 open the ticket. -->
            <td class="queue-table__check" @click.stop>
              <input
                type="checkbox"
                :checked="selectedSet.has(ticket.id)"
                :aria-label="`Select ${ticket.ticketNumber}`"
                @change="emit('toggle', ticket.id)"
              />
            </td>
            <td class="queue-table__ticket">
              <!-- The keyboard path to the ticket. A click handler on a <tr>
                   is invisible to the keyboard, and opening a ticket is the
                   only thing this page is for. React made the whole row a
                   role="button" with its own key handler, which hid the row's
                   cells from a screen reader's table navigation (U2 GAP-14)
                   and had to guard the checkbox's Space key by hand. A real
                   button in the row needs neither: Tab reaches it, Enter and
                   Space open it, and the checkbox keeps its own keys. The row
                   stays a mouse target as well.
                   The accessible name is the one the e2e suite clicks
                   (frontend/e2e/tickets.spec.ts): "Open SUP-YYYY-NNNNN". -->
              <button
                type="button"
                class="queue-table__open"
                :aria-label="`Open ${ticket.ticketNumber}`"
                @click.stop="openFromButton($event, ticket.id)"
              >
                {{ ticket.ticketNumber }}
              </button>
            </td>
            <td class="queue-table__nowrap">
              <!-- No requester at all on tickets the platform raised itself. -->
              <template v-if="ticket.user.name !== null">{{ ticket.user.name }}</template>
              <template v-else>
                <span class="queue-table__muted" aria-hidden="true">—</span>
                <span class="sr-only">No requester</span>
              </template>
              <span v-if="ticket.user.region" class="queue-table__region">{{
                ticket.user.region
              }}</span>
            </td>
            <!-- Cut off at a fixed width. The title carries the whole subject,
                 which React left unreadable short of opening the ticket
                 (U2 GAP-13). -->
            <td class="queue-table__subject" :title="ticket.subject">{{ ticket.subject }}</td>
            <td>
              <span class="queue-table__badges">
                <TicketStatusBadge :status="ticket.status" />
                <OverdueBadge v-if="ticket.overdue" />
              </span>
            </td>
            <td>
              <TicketPriorityBadge :priority="ticket.priority" />
            </td>
            <td class="queue-table__nowrap">
              <template v-if="ticket.assignee">{{ ticket.assignee.name }}</template>
              <span v-else class="queue-table__muted">Unassigned</span>
            </td>
            <!-- The support clock: internal notes count as activity here,
                 which is why it is not the same column the requester sees. -->
            <td class="queue-table__nowrap queue-table__muted queue-table__when">
              {{ formatWhen(ticket.supportUpdatedAt) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import TicketPriorityBadge from '@/components/support/TicketPriorityBadge.vue'
import TicketStatusBadge from '@/components/support/TicketStatusBadge.vue'
import type { TicketRow } from '@/utils/ticketAgentSchema'
import OverdueBadge from './OverdueBadge.vue'

const props = defineProps<{
  tickets: TicketRow[]
  loading: boolean
  failed: boolean
  selectedIds: number[]
  /** True only on a page that continues the frozen walk. An empty page there
   *  is not the same claim as an empty queue, so it does not get the same
   *  sentence. A page reached by clicking its number is a fresh read, so it
   *  is not one of these. */
  continuesWalk: boolean
}>()

const emit = defineEmits<{
  toggle: [id: number]
  'toggle-all': []
  open: [id: number]
}>()

const selectedSet = computed(() => new Set(props.selectedIds))

// Against the rows on screen, not against the whole selection, which
// survives paging on purpose.
const allOnPage = computed(
  () => props.tickets.length > 0 && props.tickets.every((t) => selectedSet.value.has(t.id))
)
const someOnPage = computed(() => props.tickets.some((t) => selectedSet.value.has(t.id)))

// A click anywhere else on the row opens the ticket too. Focus goes to the
// row's own button first, so the panel has a real control to hand focus back
// to when it closes, and a keyboard user who switches from the mouse carries
// on from the row they opened.
function openFromRow(event: MouseEvent, id: number) {
  const row = event.currentTarget as HTMLElement
  row.querySelector<HTMLButtonElement>('.queue-table__open')?.focus()
  emit('open', id)
}

// The button itself says so as well. Safari, and Firefox on macOS, do not
// focus a button that is clicked, so without this a mouse click on the
// ticket number left the panel no opener to return focus to.
function openFromButton(event: MouseEvent, id: number) {
  const button = event.currentTarget as HTMLButtonElement
  button.focus()
  emit('open', id)
}

function formatWhen(value: string) {
  return new Date(value).toLocaleString('en-AU', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    // Rendered in whatever zone the reader's machine is in, so the zone has
    // to be on screen. The same row reads 03:37 pm in Sydney and 02:37 am in
    // Sao Paulo, and agents compare these times with each other.
    timeZoneName: 'short'
  })
}
</script>

<style scoped>
/* Same frame as AdminDataTable (radius, border, head wash, cell padding), as
   a close variant rather than that component itself: its row checkboxes are
   labelled "Select row N" rather than by ticket, its rows open only by mouse,
   and its footer is Previous/Next over an offset, which this queue's walk
   cannot use.

   Muted text is a literal #616970 in light mode: --text-muted is under AA on
   these grounds. Measured: 5.58:1 on --white, 4.88:1 on the selected-row
   wash. Dark gives it back to the theme: 5.72:1 on the card, 4.95:1 on the
   wash. The ticket button is green on light (6.03:1 on --white, 5.27:1 on
   the wash) and mint on dark (6.13:1, 5.29:1): the theme does not redefine
   --dark-green, which is 2.79:1 on the dark card. */
.queue-table {
  --queue-muted: #616970;
  --queue-danger: #a71d2a;
  --queue-link: var(--dark-green);
}

:root[data-theme='dark'] .queue-table {
  --queue-muted: var(--text-muted);
  --queue-danger: var(--danger);
  --queue-link: var(--mint-green);
}

.queue-table__state {
  margin: 0;
  padding: 2rem 1rem;
  border: 1px solid var(--border-light);
  border-radius: 10px;
  background: var(--white);
  color: var(--queue-muted);
  font-size: 0.9rem;
  font-weight: 400;
  text-align: center;
}

.queue-table__state--error {
  color: var(--queue-danger);
  font-weight: 600;
}

.queue-table__scroll {
  overflow-x: auto;
  border: 1px solid var(--border-light);
  border-radius: 10px;
  background: var(--white);
}

.queue-table__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.queue-table__table th {
  padding: 0.85rem 1rem;
  background: var(--light-green);
  color: var(--charcoal);
  font-weight: 600;
  text-align: left;
  white-space: nowrap;
  border-bottom: 1px solid var(--border-light);
}

.queue-table__table td {
  padding: 0.75rem 1rem;
  color: var(--charcoal);
  font-weight: 400;
  vertical-align: middle;
  border-bottom: 1px solid var(--border-light);
}

.queue-table__table tbody tr:last-child td {
  border-bottom: none;
}

.queue-table__table .queue-table__check {
  width: 2.5rem;
  padding-right: 0.25rem;
}

.queue-table__check input {
  width: 1rem;
  height: 1rem;
  cursor: pointer;
}

.queue-table__row {
  cursor: pointer;
}

.queue-table__row:hover td,
.queue-table__row--selected td {
  background: var(--light-green);
}

.queue-table__open {
  padding: 0;
  border: none;
  background: transparent;
  color: var(--queue-link);
  font: inherit;
  font-weight: 600;
  white-space: nowrap;
  cursor: pointer;
  text-underline-offset: 2px;
}

.queue-table__open:hover {
  text-decoration: underline;
}

.queue-table__nowrap {
  white-space: nowrap;
}

/* Two classes, so it beats the cell colour above when it sits on a <td>. */
.queue-table__table .queue-table__muted {
  color: var(--queue-muted);
}

.queue-table__region {
  display: block;
  color: var(--queue-muted);
  font-size: 0.78rem;
}

.queue-table__subject {
  max-width: 22rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.queue-table__badges {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
}

.queue-table__when {
  font-size: 0.85rem;
}
</style>
