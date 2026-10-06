<template>
  <p v-if="failed" class="support-roster__error" role="alert">The roster could not be loaded.</p>
  <AdminDataTable
    v-else
    class="support-roster"
    :columns="columns"
    :rows="agents"
    :loading="loading"
    :show-pagination="false"
    empty-message="Nobody has been granted support access yet. Administrators can still work the queue."
  >
    <template #header-actions>
      <span class="sr-only">Actions</span>
    </template>

    <template #cell-name="{ row }">
      <!-- Whether this row is somebody working today. Granting and revoking
           queue access never touch the account, and switching an account off
           never touches the roster, so a name here can be an account nobody
           can sign into. The endpoint sends accountStatus for this; before
           anything read it, the row looked exactly like an agent picking up
           tickets.

           The mark is the account's own word (Suspended and Deactivated are
           different decisions and an admin acts on them differently) and it
           is absent for every status that can still sign in, invited and
           pending included. Those two are is_active=False as well, so a mark
           driven off is_active labels a colleague who has not set their
           password yet as switched off. accountStatusNote owns that rule.

           One line on purpose: the space between the two spans is what keeps
           the name and the mark apart in the text a screen reader gets. -->
      <span>{{ toAgent(row).name }}</span> <span v-if="markFor(row)" class="support-roster__mark">{{ markFor(row) }}</span>
    </template>

    <template #cell-email="{ row }">
      <span class="support-roster__email">{{ toAgent(row).email }}</span>
    </template>

    <template #cell-actions="{ row }">
      <button
        type="button"
        class="btn btn-outline btn-sm"
        :disabled="revoking"
        @click="emit('revoke', toAgent(row), $event.currentTarget as HTMLElement)"
      >
        Revoke
        <span class="sr-only">{{ toAgent(row).name }}</span>
      </button>
    </template>
  </AdminDataTable>
</template>

<script setup lang="ts">
import AdminDataTable, { type AdminColumn } from '@/components/admin/AdminDataTable.vue'
import { accountStatusNote, type SupportAgent } from '@/utils/ticketAgentSchema'

defineProps<{
  /** In the server's order. It sorts on first name, last name, then email,
   *  because "first_name alone is not a total order, and it is blank for
   *  anyone invited but never onboarded: those rows would shuffle between
   *  requests, which reads as the table losing people". Nothing here
   *  re-sorts them. */
  agents: SupportAgent[]
  loading: boolean
  failed: boolean
  revoking: boolean
}>()

const emit = defineEmits<{
  (e: 'revoke', agent: SupportAgent, opener: HTMLElement): void
}>()

// No sortable column, on purpose: see the agents prop.
const columns: AdminColumn[] = [
  { key: 'name', label: 'Name' },
  { key: 'email', label: 'Email' },
  // What revoking would strand. Resolved tickets are not counted: nobody has
  // to pick those up again.
  { key: 'openTickets', label: 'Open tickets', align: 'right' },
  { key: 'actions', label: 'Actions', width: '9rem' }
]

/** AdminDataTable hands rows back as Record<string, unknown>. */
const toAgent = (row: Record<string, unknown>) => row as unknown as SupportAgent

/** "Suspended · cannot work the queue", or null for an account that can sign in. */
function markFor(row: Record<string, unknown>) {
  const note = accountStatusNote(toAgent(row).accountStatus)
  return note ? `${note} · cannot work the queue` : null
}
</script>

<style scoped>
/* Colours come from the page (SupportAgentsPage.vue sets --roster-* for both
   themes and its spec measures them against --white and the row hover). */
.support-roster__error {
  margin: 0;
  color: var(--roster-danger);
}

.support-roster__email {
  color: var(--roster-muted);
}

.support-roster__mark {
  margin-left: 0.25rem;
  color: var(--roster-warn);
  font-size: 0.75rem;
  font-weight: 600;
}
</style>
