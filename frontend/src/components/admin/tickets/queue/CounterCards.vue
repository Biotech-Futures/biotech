<template>
  <div class="queue-cards">
    <!-- The card listens for the click so the whole card is a mouse target;
         the button inside it is what the keyboard and a screen reader reach.
         The button has no handler of its own, so a click on it reaches the
         card once. React wired both and fired the filter twice (U2 GAP-09). -->
    <div
      v-for="card in CARDS"
      :key="card.key"
      class="queue-card"
      :class="{ 'queue-card--link': card.filter }"
      @click="card.filter && emit('show', card.filter)"
    >
      <!-- A button rather than a click handler on the card alone: this has
           to be reachable from the keyboard, and a div with a click handler
           is not. -->
      <button
        v-if="card.filter"
        type="button"
        class="queue-card__label queue-card__label--button"
        :aria-describedby="`${idBase}-${card.key}-value ${idBase}-${card.key}-hint`"
      >
        {{ card.label }}
      </button>
      <p v-else class="queue-card__label">{{ card.label }}</p>

      <p
        :id="`${idBase}-${card.key}-value`"
        class="queue-card__value"
        :class="{ 'queue-card__value--alert': card.key === 'overdue' && (summary?.overdue ?? 0) > 0 }"
      >
        <!-- No number at all when we do not have one. A failed request is not
             the same as a count of zero, and "Overdue 0" is the one thing on
             this page an agent might act on by walking away. Nothing on this
             page retries on its own. The dash is drawn, not read: a screen
             reader hears "not available" instead of a punctuation name. -->
        <template v-if="hasNumbers">{{ summary![card.key] }}</template>
        <template v-else>
          <span aria-hidden="true">—</span>
          <span class="sr-only">not available</span>
        </template>
      </p>
      <p :id="`${idBase}-${card.key}-hint`" class="queue-card__hint">{{ card.hint }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, useId } from 'vue'

import { UNASSIGNED, type TicketFilters, type TicketSummary } from '@/utils/ticketAgentSchema'

const props = defineProps<{
  summary: TicketSummary | null
  loading: boolean
  failed: boolean
}>()

/** Cards a single filter reproduces exactly lead there. Overdue is the one
 *  that does not: it is worked out from the SLA clock as the queue is read,
 *  and the queue endpoint has no parameter for it. */
const emit = defineEmits<{ show: [filter: TicketFilters] }>()

const idBase = useId()

const hasNumbers = computed(() => !props.loading && !props.failed && props.summary !== null)

const CARDS: {
  key: keyof TicketSummary
  label: string
  hint: string
  /** The filter that lists what this card counts, where one exists. */
  filter?: TicketFilters
}[] = [
  {
    key: 'unassigned',
    label: 'Unassigned',
    // Resolved tickets have no owner either, but nobody has to pick them up.
    hint: 'Still needs somebody to pick it up',
    filter: { assignee: UNASSIGNED }
  },
  {
    key: 'open',
    label: 'Open',
    // Not "received, not started": a reply does not claim a ticket, and a
    // reopened one comes back here with its history intact, so this bucket
    // legitimately holds answered work too. What is true of all of them is
    // that nobody owns it.
    hint: 'Nobody has picked it up yet',
    filter: { status: 'open' }
  },
  {
    key: 'pendingUser',
    label: 'Pending user',
    hint: 'Waiting on the requester',
    filter: { status: 'pending_user' }
  },
  {
    key: 'overdue',
    label: 'Overdue',
    // Not "no first reply": that is the rule the client replaced on
    // 2026-09-04. The clock restarts every time the requester writes back, so
    // a ticket support has already answered lands here again once it sits.
    hint: 'Waiting on support for longer than its priority allows'
  }
]
</script>

<style scoped>
.queue-cards {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

@media (min-width: 1024px) {
  .queue-cards {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

/* Muted text and the Overdue number take literal colours in light mode:
   --text-muted is 4.45:1 and --danger 4.30:1 on light grounds, both under AA
   (TicketDetailPage.vue measured the same pair). On the card's --white, the
   first redesign round's #5a6268 is 6.21:1 and #a71d2a 7.36:1. Dark hands
   both back to the theme, as the designer's dark queue keeps its colours:
   --text-muted 5.72:1 and --danger 6.08:1 on the dark card. */
.queue-card {
  --queue-card-muted: #5a6268;
  --queue-card-alert: #a71d2a;

  padding: 1rem 1.125rem;
  border: 1px solid #e3e7e5;
  border-radius: 12px;
  background: var(--white);
  box-shadow: 0 1px 2px rgba(23, 66, 67, 0.06), 0 4px 12px rgba(23, 66, 67, 0.05);
}

:root[data-theme='dark'] .queue-card {
  --queue-card-muted: var(--text-muted);
  --queue-card-alert: var(--danger);

  border-color: var(--border-light);
  box-shadow: 0 1px 2px var(--shadow);
}

.queue-card--link {
  cursor: pointer;
  transition: border-color 0.18s ease;
}

.queue-card--link:hover {
  border-color: var(--dark-green);
}

/* One line height for the button and the paragraph alike, and the button a
   block of its own: an inline button sat on the card's text baseline and
   came out 5px lower than the Overdue label beside it. */
.queue-card__label {
  margin: 0;
  color: var(--queue-card-muted);
  font-size: 0.75rem;
  font-weight: 600;
  line-height: 1.4;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.queue-card__label--button {
  display: block;
  width: fit-content;
  padding: 0;
  border: none;
  background: transparent;
  font-family: inherit;
  cursor: pointer;
  text-underline-offset: 2px;
}

/* Colour and background both set, so no global hover rule can combine into
   an unreadable pair. --charcoal on --white is 11.07:1 light, 14.37:1 dark. */
.queue-card__label--button:hover {
  background: transparent;
  color: var(--charcoal);
  text-decoration: underline;
}

.queue-card__value {
  margin: 0.15rem 0 0;
  color: var(--charcoal);
  font-size: 1.75rem;
  font-weight: 600;
  line-height: 1.2;
}

.queue-card__value--alert {
  color: var(--queue-card-alert);
}

.queue-card__hint {
  margin: 0.25rem 0 0;
  color: var(--queue-card-muted);
  font-size: 0.8rem;
  font-weight: 400;
  line-height: 1.4;
}

@media (prefers-reduced-motion: reduce) {
  .queue-card--link {
    transition: none;
  }
}
</style>
