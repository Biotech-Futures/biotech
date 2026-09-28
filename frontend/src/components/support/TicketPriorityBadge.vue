<template>
  <span class="priority-badge" :class="`priority-badge--${priority}`">
    {{ priorityLabel(priority) }} priority
  </span>
</template>

<script setup lang="ts">
import { priorityLabel, type TicketPriority } from '@/utils/supportAPI'

defineProps<{ priority: TicketPriority }>()
</script>

<style scoped>
/* Deliberately quieter than TicketStatusBadge. The status is the thing a
   requester needs at a glance — whose move it is — and the priority is the
   thing they told us. Two equally loud pills next to each other would make
   the ticket look like a dashboard.

   "priority" is spelled out in the text rather than left as a bare "High",
   because "High" on its own beside a status reads like a second status.

   Normal and Low were the same mistake as the first two goes at High below,
   one step quieter. They take --text-muted, and the badge paints no
   background, so the ground is .content-area's --bg-light. #6c757d there is
   4.45:1, under the 4.5:1 this file already holds itself to, at 11.52px/600
   which is nowhere near the size that earns the large-text exemption.

   --ticket-muted is --text-muted taken 10% darker, and it clears AA on every
   ground a ticket puts muted text on. Measured:

     #616970 on #ffffff  5.58:1   on #f8f9fa  5.29:1   on #fcede2  4.88:1

   Dark keeps the theme's own --text-muted, which is 6.19:1 on --bg-light and
   5.37:1 on the requester's own message bubble. */
.priority-badge {
  --ticket-muted: #616970;

  display: inline-block;
  padding: 0.1rem 0.5rem;
  border-radius: 999px;
  border: 1px solid var(--border-light);
  background: transparent;
  color: var(--ticket-muted);
  font-size: 0.72rem;
  font-weight: 600;
  line-height: 1.6;
  white-space: nowrap;
}

:root[data-theme="dark"] .priority-badge {
  --ticket-muted: var(--text-muted);
}

/* Only High gets colour. Normal is the default and needs no emphasis, and
   colouring Low would draw the eye to the least urgent thing on the page.

   Two goes at this, both wrong for the same reason — assuming what is behind
   the badge.

   First a literal dark red, fine on white and 2.0:1 against the dark theme's
   surface. Then var(--danger), which IS tuned per theme, measured against
   --surface-elevated. But the badge has no background of its own, and the
   first ancestor that actually paints one is .content-area, which uses
   --bg-light: #f8f9fa in light. --danger there is 4.30:1 — under the 4.5:1
   WCAG asks for, on the one badge whose whole job is to be noticed.

   So the colour is chosen to clear AA against every ground it could sit on
   rather than against one guessed ancestor. Measured:

     light  #a71d2a on #ffffff  7.36:1   on #f8f9fa  6.98:1
     dark   #f87171 on #1d2826  5.49:1   on #0f1715  6.58:1

   The dark value is the theme's own --danger, which is already comfortable.
   Only light needed a darker red than the shared token, because that token is
   tuned for body text and this is a small bold pill. */
.priority-badge--high {
  --badge-danger: #a71d2a;
  border-color: var(--badge-danger);
  color: var(--badge-danger);
}

:root[data-theme="dark"] .priority-badge--high {
  --badge-danger: var(--danger);
}
</style>
