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
      <span class="support-roster__name">{{ toAgent(row).name }}</span> <span v-if="markFor(row)" class="support-roster__mark">{{ markFor(row) }}</span>
    </template>

    <template #cell-email="{ row }">
      <span class="support-roster__email">{{ toAgent(row).email }}</span>
    </template>

    <template #cell-actions="{ row }">
      <button
        type="button"
        class="btn btn-outline btn-sm support-roster__revoke"
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
   themes and its spec measures them against --white and the row hover).

   The first redesign round (October 2026) frames this table the way it does
   the ticket queue: a pale green head in small capitals, a softer edge and
   shadow, the name in bold and a neutral Revoke. AdminDataTable is Team 1's
   and every admin list uses it, so all of that is written here, against this
   table only: the root carries this component's scope id and the class
   below, which outrank that component's own rules. Its head is centred by
   the admin portal's convention; this one reads left like the queue, with
   the count on the right over its numbers. */
.admin-table.support-roster {
  border-color: #e3e7e5;
  border-radius: 12px;
  box-shadow: 0 1px 2px rgba(23, 66, 67, 0.06), 0 4px 12px rgba(23, 66, 67, 0.05);
}

:root[data-theme='dark'] .admin-table.support-roster {
  border-color: var(--border-light);
}

.support-roster :deep(.admin-table__head) {
  padding: 0.625rem 1.125rem;
  border-bottom: 1px solid #e6eae8;
  background-color: #dff1e8;
  color: var(--roster-head);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-align: left;
  text-transform: uppercase;
}

.support-roster :deep(.admin-table__head--right) {
  text-align: right;
}

:root[data-theme='dark'] .support-roster :deep(.admin-table__head) {
  border-bottom-color: var(--border-light);
  background-color: var(--light-green);
}

.support-roster :deep(.admin-table__cell) {
  padding: 0.69rem 1.125rem;
  border-bottom-color: #e6eae8;
  font-size: 0.9rem;
}

.support-roster :deep(.admin-table__cell--right) {
  font-size: 0.875rem;
}

:root[data-theme='dark'] .support-roster :deep(.admin-table__cell) {
  border-bottom-color: var(--border-light);
}

/* The frame draws the last line. */
.support-roster :deep(.admin-table__row:last-child .admin-table__cell) {
  border-bottom: none;
}

.support-roster__error {
  margin: 0;
  color: var(--roster-danger);
}

.support-roster__name {
  font-weight: 700;
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

/* Neutral, not green: taking access away is not the page's main action.
   Its edge is measured against the row around it, which turns peach under
   the pointer. #84938f is 2.80:1 there, so this takes --roster-row-edge,
   #7a8884 (3.23:1 on the peach, 3.70:1 on white). The extra classes outrank
   the page's dark rule that turns every outline button mint, which this one
   should not be. */
.support-roster__revoke {
  min-height: 2rem;
  padding: 0 0.75rem;
  border: 1px solid var(--roster-row-edge);
  border-radius: 8px;
  background-color: var(--white);
  color: var(--charcoal);
  font-size: 0.85rem;
  font-weight: 700;
}

:root[data-theme='dark'] .support-roster .admin-table__cell .support-roster__revoke {
  color: var(--charcoal);
}
</style>
