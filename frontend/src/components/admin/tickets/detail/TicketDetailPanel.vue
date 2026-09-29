<template>
  <aside class="ticket-detail-placeholder" aria-label="Ticket detail">
    <p>Ticket {{ ticketId }}. The detail panel is being ported.</p>
    <button type="button" class="btn btn-outline btn-sm" @click="emit('close')">Close</button>
  </aside>
</template>

<script setup lang="ts">
// Placeholder that fixes the contract between the queue page and the panel,
// so the two can be built at the same time. The DETAIL owner replaces the
// body; the props and events below are what the queue page relies on.
//
// ticketId  - the ticket to show; the panel loads its own data.
// canDelete - the server's admin flag (auth.isTicketAdmin): only admins may
//             delete, the endpoint is IsAdminScoped.
// close     - the agent dismissed the panel.
// changed   - a write went through; the queue reloads rows and counters.
// deleted   - the ticket is gone; the queue closes the panel and reloads.
defineProps<{ ticketId: number; canDelete: boolean }>()
const emit = defineEmits<{ close: []; changed: []; deleted: [id: number] }>()
</script>
