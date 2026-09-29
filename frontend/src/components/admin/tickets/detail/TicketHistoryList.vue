<template>
  <section class="ticket-history" :aria-labelledby="headingId">
    <h3 :id="headingId" class="ticket-history__heading">History</h3>

    <!-- T08: the React list printed "Nothing recorded yet." when the request
         failed, which is false, and with retries off it never recovered. A
         failure says so and offers another go. -->
    <div v-if="state === 'failed'" class="ticket-history__failed">
      <p class="ticket-history__error" role="alert">The history could not be loaded.</p>
      <button type="button" class="ticket-history__retry" @click="emit('retry')">Try again</button>
    </div>
    <p v-else-if="entries === null" class="ticket-history__quiet">Loading…</p>
    <!-- The same AuditLog rows the audit page lists, for one ticket instead
         of all of them, so they are named the same way. This list used to
         print the stored action and call every empty actor "system": one
         screen said "Status changed by Sam Reid" while this one said "status
         by system" about the row underneath it.

         Separated rather than joined with "by". The two names this can print
         that are not people, "Automated screening" and "Account removed",
         read as nonsense after "by". Action, who, when, in the audit table's
         own column order. -->
    <ul v-else-if="entries.length" class="ticket-history__list">
      <li v-for="entry in entries" :key="entry.id">
        <span class="ticket-history__action">{{ auditActionLabel(entry.action) }}</span>
        · {{ auditActorName(entry.actor, entry.afterState) }} ·
        <time :datetime="entry.createdAt">{{ when(entry.createdAt) }}</time>
      </li>
    </ul>
    <p v-else class="ticket-history__quiet">Nothing recorded yet.</p>
  </section>
</template>

<script setup lang="ts">
import { useId } from 'vue'

import {
  auditActionLabel,
  auditActorName,
  type TicketHistoryEntry
} from '@/utils/ticketAgentSchema'

import { when } from './ticketDetailText'

defineProps<{
  /** Null until the first answer arrives for this ticket. */
  entries: TicketHistoryEntry[] | null
  state: 'loading' | 'ready' | 'failed'
}>()

const emit = defineEmits<{ retry: [] }>()

const headingId = useId()
</script>

<style scoped>
/* #616970 and #a71d2a on the panel's #ffffff are 5.58:1 and 7.36:1; dark
   hands both back to the theme (--text-muted 5.72:1, --danger 6.08:1 on
   #161f1d). */
.ticket-history {
  --history-muted: #616970;
  --history-danger: #a71d2a;

  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

:root[data-theme='dark'] .ticket-history {
  --history-muted: var(--text-muted);
  --history-danger: var(--danger);
}

.ticket-history__heading {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--charcoal);
}

.ticket-history__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.8rem;
  color: var(--history-muted);
}

.ticket-history__action {
  font-weight: 600;
  color: var(--charcoal);
}

.ticket-history__quiet {
  margin: 0;
  font-size: 0.8rem;
  color: var(--history-muted);
}

.ticket-history__failed {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.6rem;
}

.ticket-history__error {
  margin: 0;
  font-size: 0.85rem;
  color: var(--history-danger);
}

.ticket-history__retry {
  padding: 0.3rem 0.8rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--white);
  color: var(--charcoal);
  font-family: inherit;
  font-size: 0.82rem;
  cursor: pointer;
}
</style>
