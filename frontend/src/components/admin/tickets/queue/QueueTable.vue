<template>
  <div ref="region" class="queue-table" role="region" aria-label="Tickets" tabindex="-1">
    <!-- A named region that takes focus from script only (tabindex -1, so
         it is not a Tab stop). The page sends focus here when the control
         that had it is taken away: the bulk bar after a batch goes through,
         or a ticket's row after the panel it opened closes. The region is
         there in every state below, so it is always somewhere to land. -->
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
    <!-- Under a round picture, as every empty list in the redesign is. -->
    <div v-else-if="!tickets.length" class="queue-table__state queue-table__state--empty">
      <span class="queue-table__empty-icon"><TicketIcon name="search" :size="22" /></span>
      <p>
        {{
          continuesWalk
            ? 'Nothing left on this page. The tickets that were here have been worked on since you opened the queue, which moves them to the front of it. Go back to page 1 to see them.'
            : 'No tickets match these filters.'
        }}
      </p>
    </div>

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
            <!-- Two lines at most, then cut off. The title carries the whole
                 subject, which React left unreadable short of opening the
                 ticket (U2 GAP-13). The span does the clamping: a cell made a
                 -webkit-box stops being a table cell. -->
            <td class="queue-table__subject" :title="ticket.subject">
              <span class="queue-table__subject-text">{{ ticket.subject }}</span>
            </td>
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
import { computed, useTemplateRef } from 'vue'

import TicketIcon from '@/components/support/TicketIcon.vue'
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

const region = useTemplateRef<HTMLDivElement>('region')

defineExpose({
  /** Put focus on the table as a whole (see the region in the template). */
  focus: () => region.value?.focus()
})

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
   cannot use. The first redesign round (October 2026) took it further from
   that frame: a pale green head in small capitals, a softer edge and shadow,
   tighter rows so the whole table fits a 1440px screen, Last activity
   included.

   Muted text is a literal in light mode: --text-muted is under AA on these
   grounds. The redesign's #5a6268 is 6.21:1 on --white and 5.43:1 on the
   selected-row wash. Dark gives it back to the theme, as the designer's dark
   queue keeps its colours: 5.72:1 on the card, 4.95:1 on the wash. The head
   is #24524a on #dff1e8 (7.51:1) in light and keeps the theme's charcoal on
   its green wash in dark. The ticket button is green on light (6.03:1 on
   --white, 5.27:1 on the wash) and mint on dark (6.13:1, 5.29:1): the theme
   does not redefine --dark-green, which is 2.79:1 on the dark card. */
.queue-table {
  --queue-muted: #5a6268;
  --queue-danger: #a71d2a;
  --queue-link: var(--dark-green);
  --queue-head: #dff1e8;
  --queue-head-ink: #24524a;
  --queue-rule: #e6eae8;
  --queue-frame: #e3e7e5;
  --queue-shadow: 0 1px 2px rgba(23, 66, 67, 0.06), 0 4px 12px rgba(23, 66, 67, 0.05);
  --queue-tile: #fcede2;
  --queue-tile-ink: #017151;
}

:root[data-theme='dark'] .queue-table {
  --queue-muted: var(--text-muted);
  --queue-danger: var(--danger);
  --queue-link: var(--mint-green);
  --queue-head: var(--light-green);
  --queue-head-ink: var(--charcoal);
  --queue-rule: var(--border-light);
  --queue-frame: var(--border-light);
  --queue-shadow: none;
  --queue-tile: #143b32;
  --queue-tile-ink: #6dbfb1;
}

.queue-table__state {
  margin: 0;
  padding: 2rem 1rem;
  border: 1px solid var(--queue-frame);
  border-radius: 12px;
  background: var(--white);
  box-shadow: var(--queue-shadow);
  color: var(--queue-muted);
  font-size: 0.9rem;
  font-weight: 400;
  text-align: center;
}

.queue-table__state--error {
  color: var(--queue-danger);
  font-weight: 600;
}

.queue-table__state--empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  padding: 2.125rem 1rem 2rem;
}

.queue-table__state--empty p {
  margin: 0;
  color: var(--charcoal);
  font-size: 1rem;
}

.queue-table__empty-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 3.5rem;
  height: 3.5rem;
  border-radius: 50%;
  background: var(--queue-tile);
  color: var(--queue-tile-ink);
}

.queue-table__scroll {
  overflow-x: auto;
  border: 1px solid var(--queue-frame);
  border-radius: 12px;
  background: var(--white);
  box-shadow: var(--queue-shadow);
}

.queue-table__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

/* 43px with its rule, as the design draws it: the select-all box is the
   tallest thing in the row (16px and the browser's 3px margins). */
.queue-table__table th {
  padding: 0.625rem 0.5rem;
  background: var(--queue-head);
  color: var(--queue-head-ink);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-align: left;
  text-transform: uppercase;
  white-space: nowrap;
  border-bottom: 1px solid var(--queue-rule);
}

.queue-table__table td {
  padding: 0.45rem 0.5rem;
  color: var(--charcoal);
  font-weight: 400;
  vertical-align: middle;
  border-bottom: 1px solid var(--queue-rule);
}

.queue-table__table tbody tr:last-child td {
  border-bottom: none;
}

.queue-table__table .queue-table__check {
  width: 2.75rem;
  padding-left: 1.125rem;
  padding-right: 0.25rem;
}

/* Brand green when ticked, the way AdminDataTable's boxes are. */
.queue-table__check input {
  width: 1rem;
  height: 1rem;
  accent-color: var(--dark-green);
  cursor: pointer;
}

.queue-table__row {
  cursor: pointer;
}

/* The row, not its cells. main.css already paints a hovered row
   (`tbody tr:hover`), and in the dark theme --light-green is translucent:
   painted on the cells as well, a hovered row got the wash twice, and the
   muted text on it fell to 4.30:1. On the row itself, this rule and the
   global one set the same background on the same element, so there is one
   wash whichever of them applies. Checked by queueContrast.spec.ts. */
.queue-table__row:hover,
.queue-table__row--selected {
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
  font-size: 0.75rem;
}

.queue-table__subject {
  width: 14rem;
}

.queue-table__subject-text {
  display: -webkit-box;
  max-width: 14rem;
  overflow: hidden;
  line-height: 1.47;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
}

.queue-table__badges {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
}

.queue-table__when {
  font-size: 0.85rem;
}
</style>
