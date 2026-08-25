<template>
  <ol class="timeline">
    <li v-for="message in renderable" :key="message.id" class="timeline__row" :class="rowClass(message)">
      <!-- System notes sit centred and unattributed: they are the ticket
           telling its own story, not somebody speaking. -->
      <p v-if="message.messageType === 'system'" class="timeline__system">
        {{ message.body }}
        <time :datetime="message.createdAt">{{ formatLongDateAU(message.createdAt) }}</time>
      </p>

      <div v-else class="timeline__bubble">
        <p class="timeline__meta">
          <span class="timeline__author">{{ message.author || 'You' }}</span>
          <time :datetime="message.createdAt">{{ formatLongDateAU(message.createdAt) }}</time>
        </p>
        <p class="timeline__body">{{ message.body }}</p>

        <ul v-if="message.attachments.length" class="timeline__files">
          <li v-for="file in message.attachments" :key="file.id">
            <a :href="attachmentUrl(ticketId, file.id)" target="_blank" rel="noopener">
              <i class="fas fa-paperclip"></i>
              {{ file.filename }}
            </a>
          </li>
        </ul>
      </div>
    </li>
  </ol>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { formatLongDateAU } from '@/utils/date'
import { attachmentUrl, type TicketMessage } from '@/utils/supportAPI'

const props = defineProps<{ ticketId: number | string; messages: TicketMessage[] }>()

// Only the three types this side of the wall knows about. Internal notes are
// already stripped by the backend's queryset — that is where the rule is
// enforced, not here — but rendering nothing for a type we do not recognise
// keeps a future backend change from surfacing something by accident.
const RENDERABLE = ['user_message', 'support_reply', 'system']

const renderable = computed(() =>
  props.messages.filter((message) => RENDERABLE.includes(message.messageType))
)

function rowClass(message: TicketMessage) {
  return {
    'timeline__row--mine': message.messageType === 'user_message',
    'timeline__row--support': message.messageType === 'support_reply',
    'timeline__row--system': message.messageType === 'system'
  }
}
</script>

<style scoped>
.timeline {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.timeline__row {
  display: flex;
}

.timeline__row--mine {
  justify-content: flex-end;
}

.timeline__row--support {
  justify-content: flex-start;
}

.timeline__row--system {
  justify-content: center;
}

.timeline__bubble {
  max-width: min(38rem, 82%);
  padding: 0.75rem 1rem;
  border-radius: 10px;
  border: 1px solid var(--border-light);
  background: var(--surface-elevated);
}

.timeline__row--mine .timeline__bubble {
  background: var(--light-green);
  border-color: transparent;
}

.timeline__meta {
  display: flex;
  gap: 0.6rem;
  align-items: baseline;
  margin: 0 0 0.3rem 0;
  font-size: 0.78rem;
  color: var(--text-muted);
}

.timeline__author {
  font-weight: 700;
  color: var(--charcoal);
}

.timeline__body {
  margin: 0;
  font-size: 0.94rem;
  line-height: 1.6;
  /* Line breaks the requester typed are part of what they wrote. */
  white-space: pre-wrap;
  word-break: break-word;
}

.timeline__system {
  margin: 0;
  padding: 0.45rem 0.9rem;
  border-radius: 999px;
  background: var(--bg-light);
  color: var(--text-muted);
  font-size: 0.83rem;
  text-align: center;
}

.timeline__system time {
  margin-left: 0.5rem;
  opacity: 0.75;
}

.timeline__files {
  list-style: none;
  margin: 0.55rem 0 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.timeline__files a {
  color: var(--dark-green);
  font-size: 0.85rem;
  text-decoration: none;
}

.timeline__files a:hover {
  text-decoration: underline;
}
</style>
