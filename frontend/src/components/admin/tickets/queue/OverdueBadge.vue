<template>
  <span class="overdue-badge">Overdue</span>
</template>

<script setup lang="ts">
// The row's own `overdue` flag decides whether this is shown; nothing on the
// portal side works the rule out. The server writes it once, as the same
// queryset condition that counts the Overdue card, so the card and the rows
// cannot disagree (backend/apps/tickets/services/queue.py).
</script>

<style scoped>
/* Shaped like TicketStatusBadge next to it (the same 24px pill), in the
   priority badge's red.
   Opaque pairs for the same reason that badge gives: a translucent ground
   hands the contrast to whatever paints underneath. Measured:
     light  #a71d2a on #fde8e8  6.27:1
     dark   #f87171 on #3a1d20  5.52:1
   The dark rule stays below the light one; the extra :root selector gives
   it the specificity, source order settles the rest. */
.overdue-badge {
  display: inline-block;
  padding: 0.15rem 0.6rem;
  border-radius: 999px;
  background: #fde8e8;
  color: #a71d2a;
  font-size: 0.78rem;
  font-weight: 600;
  line-height: 1.2rem;
  white-space: nowrap;
}

:root[data-theme='dark'] .overdue-badge {
  background: #3a1d20;
  color: #f87171;
}
</style>
