<template>
  <!-- A focusable region so the table can be scrolled sideways from the
       keyboard on a narrow screen. Its links alone are not enough: a page of
       deletions has none, and What changed is the column that runs off the
       edge. -->
  <div class="audit-table" role="region" tabindex="0" :aria-labelledby="labelledby">
    <table class="audit-table__table" :aria-labelledby="labelledby" :aria-busy="loading ? 'true' : undefined">
      <thead>
        <tr>
          <th scope="col" class="audit-table__col audit-table__col--when">When</th>
          <th scope="col" class="audit-table__col audit-table__col--ticket">Ticket</th>
          <th scope="col" class="audit-table__col audit-table__col--action">Action</th>
          <th scope="col" class="audit-table__col audit-table__col--who">Who</th>
          <th scope="col" class="audit-table__col">What changed</th>
        </tr>
      </thead>
      <tbody>
        <!-- Loading and empty each print one cell across the table. Both
             spans were written for four columns once, and the Ticket column
             made five: a span left behind stops one column short of the
             edge. -->
        <tr v-if="loading" class="audit-table__state-row">
          <td :colspan="COLUMN_COUNT" class="audit-table__state">Loading…</td>
        </tr>
        <tr v-else-if="rows.length === 0" class="audit-table__state-row">
          <td :colspan="COLUMN_COUNT" class="audit-table__state">{{ emptyMessage }}</td>
        </tr>
        <template v-else>
          <tr v-for="row in rows" :key="row.id">
            <td class="audit-table__when">{{ when(row.createdAt) }}</td>
            <td class="audit-table__ticket">
              <!-- Nothing to open. This row is the record of the ticket going
                   away, so a link would send the reader after the very thing
                   the row says is gone. -->
              <span v-if="row.action === 'delete'" class="audit-table__gone">{{ ticketName(row) }}</span>
              <!-- These link even when that ticket has since been deleted,
                   which nothing on the row can tell. The detail panel answers
                   that case itself ("That ticket could not be opened. It may
                   have been deleted."). That is an answer, not a loose end to
                   tidy up here. -->
              <RouterLink
                v-else
                class="audit-table__link"
                :to="{ name: 'admin-tickets', query: { ticket: String(row.ticketId) } }"
                :title="`Open ticket ${ticketName(row)}`"
              >
                {{ ticketName(row) }}
              </RouterLink>
            </td>
            <td>{{ auditActionLabel(row.action) }}</td>
            <!-- The wording and the reasoning live in ticketAgentSchema.ts,
                 because the History list on the detail panel prints the same
                 AuditLog rows through the per-ticket endpoint and has to say
                 the same thing about them. It used to say "system". -->
            <td>{{ auditActorName(row.actor, row.afterState) }}</td>
            <td class="audit-table__summary">{{ summarise(row, people) }}</td>
          </tr>
        </template>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'

import {
  auditActionLabel,
  auditActorName,
  type AssigneeOption,
  type TicketAuditRow
} from '@/utils/ticketAgentSchema'

import { summarise, ticketName, when } from './auditRows'

const COLUMN_COUNT = 5

withDefaults(
  defineProps<{
    rows: TicketAuditRow[]
    // The assignee roster, which turns an owner id on an assign row into a
    // name.
    people: AssigneeOption[]
    loading: boolean
    emptyMessage: string
    // The id of the heading that names this table.
    labelledby?: string
  }>(),
  { labelledby: undefined }
)
</script>

<style scoped>
/* Muted text sits on this card (--white) and, under the pointer, on the
   global `tbody tr:hover` wash (--light-green). The first redesign round's
   (October 2026) #5a6268 is 6.21:1 and 5.43:1 there; --text-muted would be
   4.69:1 and 4.10:1, under AA on the hover. Since that round the table is
   framed like the queue's: a pale green head in small capitals (#24524a on
   #dff1e8, 7.51:1), a softer edge and shadow, and shorter rows.

   The link cannot keep --dark-green in the dark theme, which does not
   redefine it: 2.79:1 on the dark card. --mint-green is 6.13:1 on the card
   and 5.30:1 on the hover wash (translucent there, so measured over the card).
   Dark muted text is the theme's own, 5.72:1 and 4.95:1, and the dark head
   keeps the theme's green wash and charcoal, as the designer drew no dark
   audit page. */
.audit-table {
  --audit-muted: #5a6268;
  --audit-link: var(--dark-green);
  --audit-head: #dff1e8;
  --audit-head-ink: #24524a;
  --audit-rule: #e6eae8;

  overflow-x: auto;
  background: var(--white);
  border: 1px solid #e3e7e5;
  border-radius: 12px;
  box-shadow: 0 1px 2px rgba(23, 66, 67, 0.06), 0 4px 12px rgba(23, 66, 67, 0.05);
}

:root[data-theme='dark'] .audit-table {
  --audit-muted: var(--text-muted);
  --audit-link: var(--mint-green);
  --audit-head: var(--light-green);
  --audit-head-ink: var(--charcoal);
  --audit-rule: var(--border-light);

  border-color: var(--border-light);
  box-shadow: none;
}

.audit-table__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.audit-table__table thead {
  background: var(--audit-head);
}

/* 40px with its rule, as the design draws it. */
.audit-table__col {
  padding: 0.625rem 1.125rem;
  border-bottom: 1px solid var(--audit-rule);
  color: var(--audit-head-ink);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  white-space: nowrap;
}

.audit-table__col--when,
.audit-table__col--who {
  width: 170px;
}

.audit-table__col--ticket {
  width: 150px;
}

.audit-table__col--action {
  width: 140px;
}

.audit-table__table td {
  padding: 0.625rem 1.125rem;
  border-bottom: 1px solid var(--audit-rule);
  vertical-align: middle;
}

.audit-table__table tbody tr:last-child td {
  border-bottom: none;
}

.audit-table__when {
  color: var(--audit-muted);
  white-space: nowrap;
}

.audit-table__state {
  color: var(--audit-muted);
}

.audit-table__gone {
  color: var(--audit-muted);
}

.audit-table__link {
  color: var(--audit-link);
  font-weight: 600;
  text-decoration: none;
}

.audit-table__link:hover {
  text-decoration: underline;
  text-underline-offset: 2px;
}

/* A deletion's summary carries the subject, which is whatever the requester
   typed, and people paste links into it. One unbroken URL would otherwise
   set the column's minimum width. `anywhere` because only it lowers the
   min-content width the table is laid out from. */
.audit-table__summary {
  overflow-wrap: anywhere;
}

/* Below this the five columns do not fit; the region scrolls instead of
   squeezing every column to a word per line. */
@media (max-width: 720px) {
  .audit-table__table {
    min-width: 44rem;
  }
}

/* The global focus ring is --dark-green, 2.79:1 on the dark card and under
   the 3:1 a focus indicator needs. */
:root[data-theme='dark'] .audit-table:focus-visible,
:root[data-theme='dark'] .audit-table__link:focus-visible {
  outline-color: var(--mint-green);
}
</style>
