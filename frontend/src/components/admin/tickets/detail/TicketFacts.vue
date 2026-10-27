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
    <!-- C-39: the groups the requester is in now, named the way admins know
         them, which for an auto-named group is its number ("BTF07"). -->
    <dt>{{ groups.length > 1 ? 'Groups' : 'Group' }}</dt>
    <dd>{{ groupsText }}</dd>
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
import { computed } from 'vue'

import { categoryLabel, type TicketDetail } from '@/utils/ticketAgentSchema'

import { when, whenDate } from './ticketDetailText'

const props = defineProps<{ ticket: TicketDetail }>()

const groups = computed(() => props.ticket.requester?.groups ?? [])
const groupsText = computed(() => {
  // No list at all is a ticket the platform raised, or a backend from before
  // the list was sent: nothing is known, which is not the same as no group.
  if (!props.ticket.requester?.groups) return '—'
  return groups.value.length ? groups.value.map((group) => group.name).join(', ') : 'Not in a group'
})
</script>

<style scoped>
/* Terms in the first redesign round's (October 2026) #5a6268, 6.21:1 on the
   panel's #ffffff; dark takes the panel's #a3b3ae, 6.95:1 on #1d2826. A wider
   term column, as the design sets it, that gives way on a narrow panel. */
.ticket-facts {
  --facts-muted: #5a6268;

  display: grid;
  grid-template-columns: minmax(7rem, 9.375rem) minmax(0, 1fr);
  gap: 0.45rem 1rem;
  margin: 0;
  font-size: 0.9rem;
  color: var(--teal);
}

:root[data-theme='dark'] .ticket-facts {
  --facts-muted: #a3b3ae;
}

.ticket-facts dt {
  color: var(--facts-muted);
}

.ticket-facts dd {
  margin: 0;
  overflow-wrap: anywhere;
}
</style>
