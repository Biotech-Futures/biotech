<template>
  <section class="ticket-audit" aria-labelledby="ticket-audit-title">
    <header class="ticket-audit__head">
      <!-- An h1 although the section shell above already has one, because
           TicketsSection.spec.ts pins every tab page's title as an h1. -->
      <h1 id="ticket-audit-title" class="ticket-audit__title">Ticket audit</h1>
      <p class="ticket-audit__subtitle">
        Every recorded action, including deletions. A deleted ticket keeps its record here after it
        has left the queue.
      </p>
    </header>

    <div class="ticket-audit__filters">
      <select v-model="actionChoice" class="ticket-audit__filter" aria-label="Filter by action">
        <option value="">Any action</option>
        <option v-for="option in TICKET_AUDIT_ACTIONS" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>

      <select v-model="actorChoice" class="ticket-audit__filter" aria-label="Filter by who did it">
        <option value="">Anyone</option>
        <option v-for="person in options" :key="person.id" :value="String(person.id)">
          {{ person.name }}
        </option>
      </select>
    </div>

    <!-- Replaces the table and its footer, as it did in React. tabindex so
         that focus can be handed to it when the footer it replaces had focus
         (see load). -->
    <p v-if="failure !== null" ref="alertEl" class="ticket-audit__error" role="alert" tabindex="-1">
      <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
      <span>{{ failureMessage }}</span>
    </p>

    <template v-else>
      <TicketAuditTable
        :rows="rows"
        :people="people"
        :loading="loading"
        :empty-message="emptyMessage"
        labelledby="ticket-audit-title"
      />

      <AuditPager
        ref="pagerEl"
        :page="page"
        :total-pages="totalPages"
        :page-size="shownSize"
        :disabled="loading"
        @page-change="page = $event"
        @page-size-change="changePageSize"
      />
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import AuditPager from '@/components/admin/tickets/audit/AuditPager.vue'
import TicketAuditTable from '@/components/admin/tickets/audit/TicketAuditTable.vue'
import { actorOptions, type AuditActor } from '@/components/admin/tickets/audit/auditRows'
import { logApiError } from '@/utils/apiError'
import { fetchAssignees, fetchTicketAudit, wasRefused } from '@/utils/ticketAgentAPI'
import {
  TICKET_AUDIT_ACTIONS,
  type AssigneeOption,
  type TicketAuditPage
} from '@/utils/ticketAgentSchema'

// Filters and paging live here and not on the URL, so following a ticket link
// out of this page and pressing back lands on page 1 with no filter. In React
// that was a matter of which file could be changed. Here it is parity: the
// queue keeps its filters off the URL too (port-design.md section 6), and a
// Who filter on the URL could carry only an id, with no name to show for a
// person the reloaded page no longer has a row or a roster entry for.
const page = ref(1)
const limit = ref(25)
const action = ref('')
const actor = ref<AuditActor | null>(null)

const audit = ref<TicketAuditPage | null>(null)
const people = ref<AssigneeOption[]>([])
const loading = ref(false)
const failure = ref<unknown>(null)

const rows = computed(() => audit.value?.items ?? [])
const options = computed(() => actorOptions(people.value, rows.value, actor.value))
const actorId = computed(() => actor.value?.id ?? null)

// No sentinel value for "any": a native select holds "" happily. React needed
// `__any__` because its Select could not, and that value must never reach the
// server, which would filter on it and answer nothing.
const actionChoice = computed({
  get: () => action.value,
  set: (value: string) => {
    action.value = value
    // Page 3 of the old filter is rarely page 3 of the new one.
    page.value = 1
  }
})

// The selection is held as {id, name}, not just an id: see actorOptions.
const actorChoice = computed({
  get: () => (actor.value ? String(actor.value.id) : ''),
  set: (value: string) => {
    actor.value =
      value === '' ? null : (options.value.find((person) => String(person.id) === value) ?? null)
    page.value = 1
  }
})

function changePageSize(size: number) {
  limit.value = size
  page.value = 1
}

// The page size the server actually used, which is not always the one asked
// for. views.py clamps limit to MAX_PAGE_SIZE, 100, and answers with what it
// served; the rows-per-page control offers 200. Dividing the total by the
// asked-for size called 300 rows two pages of 200 while the server was
// sending three pages of 100, and the hundred rows past the end of page 2
// could be reached from nowhere in the footer.
//
// The control is fed the same number once the answer lands (shownSize, below)
// for the same reason: left on 200 it stands there claiming a page size the
// server is not honouring.
//
// Before the first answer there is no served size, so the asked-for one
// stands in. Never zero: that divides the total by nothing and offers
// Infinity pages.
const served = computed(() => audit.value?.limit ?? limit.value)
const totalPages = computed(() => Math.max(1, Math.ceil((audit.value?.total ?? 0) / served.value)))

// The size the answer on screen was asked for.
const answeredFor = ref<number | null>(null)

// What the rows-per-page control names: the size the server served for the
// size in force, and the size just picked while nothing has answered for it
// yet. The previous answer's size there would put the control back on 25 for
// the length of the request, right after the reader picked 50. React fell
// back to the asked size whenever it had no answer for the query, page
// changes included, so after asking for 200 its control flicked to 200 while
// any page it had not fetched before was loading. Keyed on the size rather
// than on loading, this one stays on 100.
const shownSize = computed(() =>
  answeredFor.value === limit.value ? served.value : limit.value
)

// The screening handoff is the only writer of a Created row. A ticket a
// requester submits records none, so that filter answers nothing on a
// platform with a hundred tickets on it, and a bare empty table reads as a log
// that has stopped recording.
const emptyMessage = computed(() =>
  action.value === 'create'
    ? 'Nothing recorded for this filter. Only the automated screening writes a Created row. A ticket somebody submitted from the portal does not write one.'
    : 'Nothing recorded for this filter.'
)

// A 403 is the server working as intended, not a fault: a student who types
// this address reaches the page and is refused. "Could not be loaded" would
// send them looking for a breakage that is not there.
const failureMessage = computed(() =>
  wasRefused(failure.value)
    ? 'You do not have access to the ticket audit. It is open to the support team and to administrators.'
    : 'The audit log could not be loaded.'
)

// Two changes in a row leave two requests in flight, and the slower one must
// not paint over the newer one: that would show one filter's rows under
// another filter's name. Only the latest request may write.
let latest = 0

const pagerEl = ref<InstanceType<typeof AuditPager> | null>(null)
const alertEl = ref<HTMLElement | null>(null)

// Whether keyboard focus is on something in the footer: a page button or a
// size control.
function focusInPager(): boolean {
  const footer = pagerEl.value?.$el as HTMLElement | undefined
  return footer !== undefined && footer.contains(document.activeElement)
}

async function load() {
  const token = ++latest
  loading.value = true
  failure.value = null
  // The previous answer stays until the next one arrives. Its rows are never
  // on screen meanwhile, because the table shows "Loading…" instead of rows
  // while this runs, as the React page did. What stays is the footer's count:
  // React started every page and filter from nothing, so going to page 3 of
  // 12 read "Page 3 of 1" until the answer came.
  const asked = limit.value
  try {
    const result = await fetchTicketAudit(page.value, asked, {
      action: action.value,
      actor: actorId.value === null ? '' : String(actorId.value)
    })
    if (token !== latest) return
    audit.value = result
    answeredFor.value = asked
  } catch (error) {
    if (token !== latest) return
    logApiError('Ticket audit', error)
    // The alert takes the footer's place. A failed page change is started
    // from the footer, so the button the reader pressed is removed from under
    // them and the browser drops focus to the top of the document. React did
    // the same; here focus goes to the alert instead, so a keyboard reader
    // carries on from the message rather than from the top of the page. A
    // load started from a filter leaves focus alone: the filters stay.
    const refocus = focusInPager()
    failure.value = error
    if (refocus) {
      await nextTick()
      alertEl.value?.focus()
    }
  } finally {
    if (token === latest) loading.value = false
  }
}

// Fetched every time the page opens and whenever a control changes, and at no
// other time. The React page kept each answer in a cache for the session, so
// coming back to a page already seen showed it without a deletion made in the
// meantime; there is no cache here to go stale.
watch([page, limit, action, actorId], () => void load(), { immediate: true })

// The roster turns owner ids into names and seeds the Who filter. Failing is
// not worth a message: an assign row falls back to "#11" and the filter still
// offers everybody on the rows.
onMounted(async () => {
  try {
    people.value = await fetchAssignees()
  } catch (error) {
    logApiError('Ticket assignees', error)
  }
})
</script>

<style scoped>
/* Muted text and the error line both take a literal colour rather than
   --text-muted and --danger. The ground here is the section's .content-area,
   --bg-light, where those two tokens are 4.45:1 and 4.30:1, both under AA.
   #616970 is 5.29:1 and #a71d2a 6.98:1, the values TicketDetailPage.vue uses
   for the same reason. Dark hands both back to the theme: 6.19:1 and
   6.58:1 on the dark ground. */
.ticket-audit {
  --audit-muted: #616970;
  --audit-danger: #a71d2a;

  display: flex;
  flex-direction: column;
  gap: 1rem;
}

:root[data-theme='dark'] .ticket-audit {
  --audit-muted: var(--text-muted);
  --audit-danger: var(--danger);
}

.ticket-audit__title {
  margin: 0 0 0.25rem;
  font-size: 1.5rem;
}

.ticket-audit__subtitle {
  margin: 0;
  color: var(--audit-muted);
  font-size: 0.92rem;
}

.ticket-audit__filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}

.ticket-audit__filter {
  width: 190px;
  max-width: 100%;
  height: 2.25rem;
  padding: 0.25rem 0.5rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--white);
  color: var(--charcoal);
  font: inherit;
  font-size: 0.9rem;
}

.ticket-audit__error {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0;
  padding: 0.75rem 1rem;
  border-left: 4px solid var(--audit-danger);
  border-radius: 6px;
  color: var(--audit-danger);
}

/* The global focus ring is --dark-green, which the dark theme does not
   redefine: 2.79:1 on the dark surface, under the 3:1 a focus indicator
   needs. --mint-green is 6.13:1 there. */
:root[data-theme='dark'] .ticket-audit__filter:focus-visible,
:root[data-theme='dark'] .ticket-audit__error:focus-visible {
  outline-color: var(--mint-green);
}

@media (max-width: 640px) {
  .ticket-audit__filter {
    width: 100%;
  }
}
</style>
