<template>
  <dl class="ticket-facts">
    <dt>Requester</dt>
    <!-- Null on a ticket the platform's own message screening raised: nobody
         filled in a form for it. -->
    <dd>{{ ticket.requester?.name ?? '—' }}</dd>
    <dt>Email</dt>
    <dd>{{ ticket.requester?.email ?? '—' }}</dd>
    <dt>Member since</dt>
    <dd>{{ ticket.requester ? whenDate(ticket.requester.registeredAt) : '—' }}</dd>
    <dt>Region</dt>
    <dd>{{ ticket.region || 'Unknown' }}</dd>
    <dt>Category</dt>
    <dd>{{ categoryLabel(ticket.category) }}</dd>
    <dt>Channel</dt>
    <dd>{{ ticket.channel }}</dd>
    <dt>Raised</dt>
    <dd>{{ when(ticket.createdAt) }}</dd>
    <dt>First reply</dt>
    <dd>{{ ticket.firstResponseAt ? when(ticket.firstResponseAt) : 'Not yet' }}</dd>
    <dt>Resolved</dt>
    <dd>{{ ticket.resolvedAt ? when(ticket.resolvedAt) : '—' }}</dd>
    <!-- p49 lists Category, Created and Updated as the panel's read-only
         fields. Shows the support-side clock, which is the one this panel is
         about: the requester-facing clock (updatedAt) deliberately ignores
         internal notes and hand-offs, so an agent reading "Updated" here
         wants to know when anything last happened. -->
    <dt>Updated</dt>
    <dd>{{ when(ticket.supportUpdatedAt) }}</dd>
  </dl>
</template>

<script setup lang="ts">
import { categoryLabel, type TicketDetail } from '@/utils/ticketAgentSchema'

import { when, whenDate } from './ticketDetailText'

defineProps<{ ticket: TicketDetail }>()
</script>

<style scoped>
/* Terms in #616970, 5.58:1 on the panel's #ffffff; dark hands them back to
   --text-muted, 5.72:1 on #161f1d. */
.ticket-facts {
  --facts-muted: #616970;

  display: grid;
  grid-template-columns: minmax(7rem, max-content) minmax(0, 1fr);
  gap: 0.4rem 1rem;
  margin: 0;
  font-size: 0.88rem;
  color: var(--charcoal);
}

:root[data-theme='dark'] .ticket-facts {
  --facts-muted: var(--text-muted);
}

.ticket-facts dt {
  color: var(--facts-muted);
}

.ticket-facts dd {
  margin: 0;
  overflow-wrap: anywhere;
}
</style>
