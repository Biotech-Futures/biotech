<template>
  <section class="ticket-history" :aria-labelledby="headingId">
    <!-- tabindex="-1" so Try again can hand focus here: see retry. -->
    <h3 :id="headingId" ref="headingEl" class="ticket-history__heading" tabindex="-1">History</h3>

    <!-- T08: the React list printed "Nothing recorded yet." when the request
         failed, which is false, and with retries off it never recovered. A
         failure says so and offers another go. -->
    <div v-if="state === 'failed'" class="ticket-history__failed">
      <p class="ticket-history__error" role="alert">The history could not be loaded.</p>
      <button type="button" class="ticket-history__retry" @click="retry">Try again</button>
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
import { nextTick, ref, useId } from 'vue'

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
const headingEl = ref<HTMLElement | null>(null)

// Try again is gone as soon as it is pressed: the panel starts the read
// again, and "Loading…" takes the button's place. Focus would go with it, to
// the page body and out of the modal panel. It goes to the History heading
// instead, which stays through every state: from there the list that comes
// back is next in reading order, and a second failure is announced by its
// role="alert". Only when the button really has gone, so a parent that did
// not start a new read leaves focus where it was. The same care as the
// assignee list's Try again in TicketDetailPanel.vue.
async function retry(event: MouseEvent) {
  const pressed = event.currentTarget as HTMLElement
  emit('retry')
  await nextTick()
  if (!pressed.isConnected) headingEl.value?.focus()
}
</script>

<style scoped>
/* #5a6268 and #a71d2a on the panel's #ffffff are 6.21:1 and 7.36:1; dark
   takes the panel's #a3b3ae (6.95:1 on #1d2826) and hands the error back to
   the theme (--danger 5.49:1). Since the first redesign round (October 2026)
   a rule sets the history off from the facts above it, and each entry hangs
   off a dot on a thin line: a timeline. The dot is the panel's accent, brand
   green in light and mint in dark (5.52:1 there), where brand green would
   be lost. */
.ticket-history {
  --history-muted: #5a6268;
  --history-danger: #a71d2a;
  --history-rule: #e6eae8;
  --history-dot: #017151;

  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding-top: 1.25rem;
  border-top: 1px solid var(--history-rule);
}

:root[data-theme='dark'] .ticket-history {
  --history-muted: #a3b3ae;
  --history-danger: var(--danger);
  --history-rule: #2b3936;
  --history-dot: #5ea99e;
}

.ticket-history__heading {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--charcoal);
}

.ticket-history__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  font-size: 0.85rem;
  color: var(--history-muted);
}

/* Padding, not spaces, sets the words in from the dot, so an entry that
   wraps keeps its second line under the first. */
.ticket-history__list li {
  position: relative;
  padding: 0 0 0.45rem 1.25rem;
  line-height: 1.6;
}

.ticket-history__list li::before {
  content: '';
  position: absolute;
  top: 0.45rem;
  left: 0.2rem;
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 50%;
  background: var(--history-dot);
}

/* The thread between one dot and the next, stopping short of both. */
.ticket-history__list li:not(:last-child)::after {
  content: '';
  position: absolute;
  top: 1.1rem;
  bottom: 0.05rem;
  left: calc(0.45rem - 0.5px);
  border-left: 1px solid var(--history-rule);
}

.ticket-history__action {
  font-weight: 600;
  color: var(--charcoal);
}

.ticket-history__quiet {
  margin: 0;
  font-size: 0.85rem;
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
  border-radius: 8px;
  background: var(--white);
  color: var(--charcoal);
  font-family: inherit;
  font-size: 0.82rem;
  cursor: pointer;
}
</style>
