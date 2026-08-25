<template>
  <span class="ticket-badge" :class="`ticket-badge--${status}`">{{ statusLabel(status) }}</span>
</template>

<script setup lang="ts">
import { statusLabel, type TicketStatus } from '@/utils/supportAPI'

defineProps<{ status: TicketStatus }>()
</script>

<style scoped>
/* Palette shared with the support queue in the admin app: green while it is
   ours to move, amber while it is the requester's, grey once it is done. */
.ticket-badge {
  display: inline-block;
  padding: 0.15rem 0.6rem;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 600;
  line-height: 1.6;
  white-space: nowrap;
}

.ticket-badge--open {
  background: var(--light-green);
  color: var(--dark-green);
}

.ticket-badge--in_progress {
  background: rgba(57, 104, 123, 0.14);
  color: var(--air-force-blue);
}

.ticket-badge--pending_user {
  background: rgba(255, 193, 7, 0.18);
  color: #8a6100;
}

.ticket-badge--resolved {
  background: var(--border-light);
  color: var(--text-muted);
}
</style>
