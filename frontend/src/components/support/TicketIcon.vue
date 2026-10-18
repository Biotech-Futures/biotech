<template>
  <svg
    class="ticket-icon"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    focusable="false"
  >
    <path v-for="(d, index) in TICKET_ICON_PATHS[name]" :key="index" :d="d" />
  </svg>
</template>

<script setup lang="ts">
// The thin outline icons from the first redesign round (October 2026). The
// portal's Font Awesome is the free set, which draws these shapes solid or not
// at all, so the ticket screens carry their own. The outlines follow the
// Lucide icon set's style (lucide.dev, ISC licence); each circle and box is
// written out as a path so one loop draws every icon.
//
// Every icon here sits beside words that already say what it means, so it is
// hidden from screen readers and never takes focus.
import { TICKET_ICON_PATHS, type TicketIconName } from './ticketIcons'

withDefaults(defineProps<{ name: TicketIconName; size?: number }>(), { size: 16 })
</script>

<style scoped>
.ticket-icon {
  display: inline-block;
  flex: none;
  vertical-align: middle;
}
</style>
