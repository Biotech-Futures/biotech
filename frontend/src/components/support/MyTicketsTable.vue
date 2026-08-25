<template>
  <div class="my-tickets">
    <table v-if="tickets.length" class="my-tickets__table">
      <thead>
        <tr>
          <th scope="col">Ticket ID</th>
          <th scope="col">Subject</th>
          <th scope="col">Category</th>
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
import { categoryLabel, type TicketRow } from '@/utils/supportAPI'

defineProps<{ tickets: TicketRow[] }>()
</script>

<style scoped>
.my-tickets__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.92rem;
}

.my-tickets__table th {
  text-align: left;
  padding: 0.65rem 0.75rem;
  border-bottom: 2px solid var(--border-light);
  color: var(--text-muted);
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

.my-tickets__id a:hover,
.my-tickets__subject:hover {
  text-decoration: underline;
}

.my-tickets__empty {
  padding: 1.5rem 0;
  color: var(--text-muted);
}

/* The table would otherwise force the page to scroll sideways on a phone. */
@media (max-width: 720px) {
  .my-tickets {
    overflow-x: auto;
  }

  .my-tickets__table {
    min-width: 560px;
  }
}
</style>
