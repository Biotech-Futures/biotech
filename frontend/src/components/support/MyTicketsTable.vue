<template>
  <div class="my-tickets">
    <table v-if="tickets.length" class="my-tickets__table">
      <thead>
        <tr>
          <th scope="col">Ticket ID</th>
          <th scope="col">Subject</th>
          <th scope="col">Category</th>
          <th scope="col">Priority</th>
          <th scope="col">Status</th>
          <th scope="col">Last updated</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="ticket in tickets" :key="ticket.id">
          <td class="my-tickets__id">
            <RouterLink :to="`/support/tickets/${ticket.id}`">#{{ ticket.ticketNumber }}</RouterLink>
          </td>
          <td>
            <RouterLink :to="`/support/tickets/${ticket.id}`" class="my-tickets__subject">
              {{ ticket.subject }}
            </RouterLink>
          </td>
          <td>{{ categoryLabel(ticket.category) }}</td>
          <td>{{ priorityLabel(ticket.priority) }}</td>
          <td><TicketStatusBadge :status="ticket.status" /></td>
          <td>{{ formatDateAU(ticket.lastUpdated) }}</td>
        </tr>
      </tbody>
    </table>

    <div v-else class="my-tickets__empty">
      <span class="my-tickets__empty-icon"><TicketIcon name="message" :size="22" /></span>
      <p>You have not raised any enquiries yet.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'
import TicketIcon from '@/components/support/TicketIcon.vue'
import TicketStatusBadge from '@/components/support/TicketStatusBadge.vue'
import { formatDateAU } from '@/utils/date'
import { categoryLabel, priorityLabel, type TicketRow } from '@/utils/supportAPI'

defineProps<{ tickets: TicketRow[] }>()
</script>

<style scoped>
/* The first redesign round (October 2026) draws this table edge to edge in
   its card, under a pale green head row with small capitals. The head's
   colours are this component's own, not the global thead's --light-green,
   which is peach in light and translucent in dark. A row under the pointer
   still takes main.css's tbody tr:hover wash in that token.

   Measured against the grounds they sit on (WCAG AA, 4.5:1 for text):
     light  head #24524a on #dff1e8 7.51:1   date #5a6268 on the #ffffff card 6.21:1
     dark   head #b4c2be on #2a3633 6.81:1   date #a3b3ae on the #1d2826 card 6.95:1
   Links are brand green in light (6.03:1 on the card) and the designer's
   #6dbfb1 in dark, where brand green on the card was 2.52:1. On a hovered
   row the date and the links are 5.43:1 and 5.27:1 on the peach, and 6.06:1
   and 6.13:1 on the dark wash (#18352e). */
.my-tickets {
  --ticket-muted: #5a6268;
  --my-tickets-head: #dff1e8;
  --my-tickets-head-ink: #24524a;
  --my-tickets-rule: #e6eae8;
  --my-tickets-link: var(--dark-green);
  --my-tickets-tile: #fcede2;
  --my-tickets-tile-ink: #017151;
}

:root[data-theme="dark"] .my-tickets {
  --ticket-muted: #a3b3ae;
  --my-tickets-head: #2a3633;
  --my-tickets-head-ink: #b4c2be;
  --my-tickets-rule: #2b3936;
  --my-tickets-link: #6dbfb1;
  --my-tickets-tile: #143b32;
  --my-tickets-tile-ink: #6dbfb1;
}

.my-tickets__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.my-tickets__table thead {
  background: var(--my-tickets-head);
}

.my-tickets__table th {
  text-align: left;
  padding: 0.75rem;
  border-top: 1px solid var(--my-tickets-rule);
  border-bottom: 1px solid var(--my-tickets-rule);
  color: var(--my-tickets-head-ink);
  font-weight: 700;
  font-size: 0.73rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.my-tickets__table td {
  padding: 0.95rem 0.75rem;
  border-bottom: 1px solid var(--my-tickets-rule);
  vertical-align: middle;
}

/* The card around the table has no side padding of its own here, so the
   outer columns carry it, in line with the card's title. */
.my-tickets__table th:first-child,
.my-tickets__table td:first-child {
  padding-left: 1.75rem;
}

.my-tickets__table th:last-child,
.my-tickets__table td:last-child {
  padding-right: 1.75rem;
}

/* The band under the table draws the last line. */
.my-tickets__table tbody tr:last-child td {
  border-bottom: none;
}

.my-tickets__table td:last-child {
  color: var(--ticket-muted);
}

/* One line each, as the design draws every row. Long subjects take the slack;
   without this the table squeezed the ticket number to its break at the
   hyphen and the head words onto two lines. */
.my-tickets__table th,
.my-tickets__id,
.my-tickets__table td:last-child {
  white-space: nowrap;
}

.my-tickets__id a,
.my-tickets__subject {
  color: var(--my-tickets-link);
  text-decoration: none;
  font-weight: 600;
}

/* A subject is whatever the requester typed, and people paste links into
   them. One unbroken 200-character URL sets the column's minimum width, and
   the table stops fitting anywhere. `anywhere` rather than `break-word`
   because only `anywhere` lowers the min-content width, which is the number
   the table is laid out from. */
.my-tickets__subject {
  overflow-wrap: anywhere;
}

.my-tickets__id a:hover,
.my-tickets__subject:hover {
  text-decoration: underline;
}

/* Centred under a round picture, as every empty list in the redesign is. */
.my-tickets__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.6rem;
  padding: 1.9rem 1.75rem;
  text-align: center;
}

.my-tickets__empty p {
  margin: 0;
  color: var(--charcoal);
}

.my-tickets__empty-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 3.5rem;
  height: 3.5rem;
  border-radius: 50%;
  background: var(--my-tickets-tile);
  color: var(--my-tickets-tile-ink);
}

/* The table scrolls inside its own box whenever it is wider than the space it
   has, at every width and not only on a phone.

   It used to be a phone-only rule, and above 720px the wrapper was
   overflow: visible, so the nearest scrolling ancestor was .content-area:
   between roughly 769px and 890px the table ran past the right edge and took
   the whole column with it, form and help card included, behind a scrollbar
   macOS keeps hidden until you scroll. Six columns need about 560px and a
   tablet in portrait or a half-width laptop window does not have it. */
.my-tickets {
  overflow-x: auto;
}

@media (max-width: 720px) {
  .my-tickets__table {
    min-width: 560px;
  }
}
</style>
