<template>
  <span class="ticket-badge" :class="`ticket-badge--${status}`">{{ statusLabel(status) }}</span>
</template>

<script setup lang="ts">
import { statusLabel, type TicketStatus } from '@/utils/supportAPI'

defineProps<{ status: TicketStatus }>()
</script>

<style scoped>
/* Green while it is ours to move, amber while it is the requester's, grey once
   it is done. The admin queue reads the same way but does not share these
   values: each app now picks colours that clear 4.5:1 against its own ground,
   and those grounds are different.

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
     end that: one status, one theme, one number. The values below are what the
     old translucent colours already composited to, so nothing looks different.

   Measured, all eight against the 4.5:1 AA threshold for text this size:
     light  open 5.27  in progress 5.03  pending user 5.04  resolved 4.70
     dark   open 4.82  in progress 5.33  pending user 5.97  resolved 5.03

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
  line-height: 1.6;
  white-space: nowrap;
}

.ticket-badge--open {
  background: #fcede2;
  color: #017151;
}

.ticket-badge--in_progress {
  background: #e4eaed;
  color: #39687b;
}

.ticket-badge--pending_user {
  background: #fff4d2;
  color: #8a6100;
}

.ticket-badge--resolved {
  background: #e0e0e0;
  color: #5a6268;
}

:root[data-theme='dark'] .ticket-badge--open {
  background: #18352e;
  color: #5ea99e;
}

:root[data-theme='dark'] .ticket-badge--in_progress {
  background: #213132;
  color: #60a5fa;
}

:root[data-theme='dark'] .ticket-badge--pending_user {
  background: #464420;
  color: #fbbf24;
}

:root[data-theme='dark'] .ticket-badge--resolved {
  background: #1f2a28;
  color: #8a9a96;
}
</style>
