<template>
  <span class="ticket-badge" :class="`ticket-badge--${status}`">{{ statusLabel(status) }}</span>
</template>

<script setup lang="ts">
import { statusLabel, type TicketStatus } from '@/utils/supportAPI'

defineProps<{ status: TicketStatus }>()
</script>

<style scoped>
/* Green while it is ours to move, amber while it is the requester's, grey once
   it is done. The student's pages, the queue and the detail panel all show
   this one component, so a status reads the same everywhere.

   Both halves of every pair are written here, opaque, rather than taken from
   the global tokens. Two reasons, both measured:

   * The dark theme redefines --light-green to rgba(1, 113, 81, 0.18) and does
     not redefine --dark-green, so the dark badge was dark green text on dark
     green: 2.19:1 on a card, 2.62:1 on the page. --air-force-blue is missing
     from the dark block too (in progress, 2.22:1), and pending user's #8a6100
     was never a token at all (1.81:1, the worst of the four). Adding the
     missing tokens to the dark block is the wrong repair: var(--dark-green)
     appears 110 times across 20 files, and this badge is not worth changing
     what all of them mean.
   * A translucent background hands the contrast to whichever ancestor happens
     to paint underneath, which is not this component's to know. Opaque values
     end that: one status, one theme, one number.

   The values are the designer's. His second round (October 2026) settles one
   colour per status, the same on every ticket screen: open a pale green
   (it was the peach the client asked us to drop, C-20), in progress solid
   brand green with white text in both themes, pending user and resolved as
   they were. Dark open keeps its ground and takes his slightly softer green
   text. The line height gives his 24px pill.

   Measured, all eight against the 4.5:1 AA threshold for text this size:
     light  open #017151 on #d3ece0 4.84   in progress #ffffff on #017151 6.03
            pending user #7a5600 on #fff4d2 6.05   resolved #4f575c on #e6e8e9 5.99
     dark   open #8fcabe on #18352e 7.16   in progress #ffffff on #017151 6.03
            pending user #fbbf24 on #3f3a17 6.88   resolved #b4c2be on #2a3633 6.81

   The dark rules must stay below the light ones: same specificity would not
   be enough, but `:root[data-theme="dark"]` adds one, and source order is what
   settles the rest. TicketPriorityBadge next door learned the same lesson and
   carries the same shape. */
.ticket-badge {
  display: inline-block;
  padding: 0.15rem 0.6rem;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 600;
  line-height: 1.2rem;
  white-space: nowrap;
}

.ticket-badge--open {
  background: #d3ece0;
  color: #017151;
}

.ticket-badge--in_progress {
  background: #017151;
  color: #ffffff;
}

.ticket-badge--pending_user {
  background: #fff4d2;
  color: #7a5600;
}

.ticket-badge--resolved {
  background: #e6e8e9;
  color: #4f575c;
}

:root[data-theme='dark'] .ticket-badge--open {
  background: #18352e;
  color: #8fcabe;
}

:root[data-theme='dark'] .ticket-badge--in_progress {
  background: #017151;
  color: #ffffff;
}

:root[data-theme='dark'] .ticket-badge--pending_user {
  background: #3f3a17;
  color: #fbbf24;
}

:root[data-theme='dark'] .ticket-badge--resolved {
  background: #2a3633;
  color: #b4c2be;
}
</style>
