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

    <p v-else class="my-tickets__empty">
      You have not raised any enquiries yet.
    </p>
  </div>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'
import TicketStatusBadge from '@/components/support/TicketStatusBadge.vue'
import { formatDateAU } from '@/utils/date'
import { categoryLabel, priorityLabel, type TicketRow } from '@/utils/supportAPI'

defineProps<{ tickets: TicketRow[] }>()
</script>

<style scoped>
/* The header row sits on the global thead --light-green, where --text-muted
   is 4.10:1 and under AA. The literal is the value TicketPriorityBadge.vue
   measured. The empty line below it is on the card, --surface-elevated,
   where --text-muted is 4.69:1 and already fine.

   Dark cannot hand the colour back to the theme the way the other three
   files do. --light-green is translucent there, so the header ground is that
   green over the card rather than the page, and --text-muted lands on
   4.4938:1. This value is --text-muted taken 10% lighter, the same move that
   produced the light one: 5.38:1 on the header, 6.18:1 on the card. */
.my-tickets {
  --ticket-muted: #616970;
}

:root[data-theme="dark"] .my-tickets {
  --ticket-muted: #98a9a5;
}

.my-tickets__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.92rem;
}

.my-tickets__table th {
  text-align: left;
  padding: 0.65rem 0.75rem;
  border-bottom: 2px solid var(--border-light);
  color: var(--ticket-muted);
  font-weight: 600;
  font-size: 0.82rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.my-tickets__table td {
  padding: 0.75rem;
  border-bottom: 1px solid var(--border-light);
  vertical-align: middle;
}

.my-tickets__id a,
.my-tickets__subject {
  color: var(--dark-green);
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

.my-tickets__empty {
  padding: 1.5rem 0;
  color: var(--ticket-muted);
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
