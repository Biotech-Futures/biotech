<template>
  <div class="ticket-queue">
    <!-- An h2: the page's one h1 is the section shell's "Support queue"
         (TicketsSection.vue), and this tab sits under it. -->
    <header class="ticket-queue__header">
      <h2 class="ticket-queue__title">Ticket queue</h2>
      <p class="ticket-queue__subtitle">
        Enquiries from across the platform, most recently active first.
      </p>
    </header>

    <CounterCards
      :summary="q.summary.value"
      :loading="q.summaryLoading.value"
      :failed="q.summaryFailed.value"
      @show="showCard"
    />

    <!-- The cards show a dash in place of every number they could not get,
         and so does a card still waiting for its first answer. Nothing on
         this page retries on its own, so a failed request sat there looking
         like a slow one; the option lists below say so out loud for the same
         reason (U2 GAP-16, React had the dashes only). Not when the queue
         itself was refused: one sentence says why for the whole page. -->
    <p
      v-if="q.summaryFailed.value && !q.queueRefused.value"
      class="ticket-queue__alert"
      role="alert"
    >
      The counts above could not be loaded. Reload to try again.
    </p>

    <p v-if="q.queueFailed.value" class="ticket-queue__alert" role="alert">
      {{
        q.queueRefused.value
          ? 'You do not have access to the ticket queue. It is open to the support team and to administrators.'
          : 'The queue could not be loaded, so this page is not showing the real state of it. Reload to try again.'
      }}
    </p>

    <div class="ticket-queue__toolbar">
      <FilterBar
        :filters="q.filters.value"
        :regions="q.regions.value"
        :assignees="q.assignees.value"
        @change="q.applyFilters"
      />
      <!-- Client item C-09 (Will, 2026-09-19): "from the admin perspective,
           some export function. If we wanted just to export that table."
           Every ticket the filters above match, not only the page on screen;
           the page and the walk stay out of it (useTicketQueue exportQueue).
           aria-disabled while it runs, not disabled: disabling the button
           that was just pressed drops keyboard focus to the top of the
           document. exportQueue ignores a press while one is running. -->
      <button
        type="button"
        class="btn btn-outline btn-sm ticket-queue__export"
        :aria-disabled="q.exporting.value ? 'true' : undefined"
        @click="q.exportQueue"
      >
        <i class="fas fa-file-excel" aria-hidden="true"></i>
        <span>{{ q.exporting.value ? 'Exporting…' : 'Export to Excel' }}</span>
      </button>
    </div>

    <p v-if="q.exportError.value" class="ticket-queue__alert" role="alert">
      {{ q.exportError.value }}
    </p>

    <!-- The two option lists fail quietly on their own: an empty list looks
         exactly like a platform with nobody on it. The assignee list also
         feeds the assign controls further down this page, which is why this
         sits above them rather than inside the filter bar. -->
    <p v-if="q.listsDown.value.length" class="ticket-queue__alert" role="alert">
      {{ listsDownSentence }}
    </p>

    <!-- Two different failures, and the two belong in different places. A
         partial failure comes back as a 200, so success clears the selection
         and its message has to live outside this block to survive that. A
         rejected request (a 400 from an assignee the write path refuses, a
         dropped connection) leaves the selection there, and the message
         belongs with it: rendered outside, it outlived the bar and left an
         agent reading a warning about a batch that was no longer selected. -->
    <template v-if="q.selectedIds.value.length">
      <BulkAssignBar
        :count="q.selectedIds.value.length"
        :assignees="q.assignees.value"
        :assignees-unavailable="q.assigneesFailed.value"
        :assignees-loading="q.assigneesPending.value"
        :pending="q.bulkPending.value"
        @clear="q.clearSelection"
        @assign="assignSelected"
      />
      <p v-if="q.bulkRejected.value" class="ticket-queue__alert" role="alert">
        {{ rejectedSentence }}
      </p>
    </template>

    <!-- What a batch that went through did. React said nothing on success
         (U2 GAP-07), and the bar that held the pressed button, with its own
         live count, goes with the selection. The region is always in the
         page, empty until there is something to say: a live region added
         together with its text is often not read out. Screen-reader text
         only, because on screen the bar going and the rows changing already
         say it. It lives as long as the partial-failure line below. -->
    <p class="sr-only" role="status">{{ assignedSentence }}</p>

    <p v-if="q.bulkFailures.value.length" class="ticket-queue__alert" role="alert">
      {{ partialFailureSentence }}
    </p>

    <QueueTable
      ref="queueTable"
      :tickets="q.tickets.value"
      :loading="q.queueLoading.value"
      :failed="q.queueFailed.value"
      :selected-ids="q.selectedIds.value"
      :continues-walk="q.continuesWalk.value"
      @toggle="q.toggle"
      @toggle-all="q.toggleAll"
      @open="openTicket"
    />

    <QueuePager
      :page="q.page.value"
      :total-pages="q.totalPages.value"
      :page-size="q.limit.value"
      :disabled="q.queueLoading.value"
      @page-change="q.goToPage"
      @page-size-change="q.setPageSize"
    />

    <!-- The panel loads its own ticket and its own roster (fresh on every
         open, so a grant or revoke on the roster is never stale there). The
         queue only says which ticket, whether this person may delete, and
         reloads when the panel reports a write. -->
    <TicketDetailPanel
      v-if="openTicketId !== null"
      :ticket-id="openTicketId"
      :can-delete="auth.isTicketAdmin"
      @close="onPanelClose"
      @changed="q.refresh"
      @deleted="onDeleted"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, useTemplateRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import TicketDetailPanel from '@/components/admin/tickets/detail/TicketDetailPanel.vue'
import BulkAssignBar from '@/components/admin/tickets/queue/BulkAssignBar.vue'
import CounterCards from '@/components/admin/tickets/queue/CounterCards.vue'
import FilterBar from '@/components/admin/tickets/queue/FilterBar.vue'
import QueuePager from '@/components/admin/tickets/queue/QueuePager.vue'
import QueueTable from '@/components/admin/tickets/queue/QueueTable.vue'
import { ticketIdFromQuery } from '@/components/admin/tickets/queue/queueRules'
import { describeFailure, useTicketQueue } from '@/composables/admin/useTicketQueue'
import { useAuthStore } from '@/stores/auth'
import type { TicketFilters } from '@/utils/ticketAgentSchema'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

// Filters, page and page size are not in the address bar: reloading the page
// returns to page one, ten rows, no filters, as the React queue did. A cursor
// in a URL goes stale, and the walk (useTicketQueue) is what holds a place.
const q = useTicketQueue()

const queueTable = useTemplateRef<InstanceType<typeof QueueTable>>('queueTable')

// Only `?ticket=` lives in the URL, and only a plain positive integer counts.
const openTicketId = computed(() => ticketIdFromQuery(route.query.ticket))

// Focus that was on a control this page has just taken away (the browser puts
// it on <body>, the top of the document) goes to the table instead, so a
// keyboard or screen-reader user carries on from the queue rather than from
// the top of the page. Focus that is anywhere else is left where it is.
function catchDroppedFocus() {
  const active = document.activeElement
  if (active === null || active === document.body) queueTable.value?.focus()
}

// `replace`, as React did: opening and closing a ticket does not add history,
// so Back leaves the queue rather than stepping through every ticket opened.
function openTicket(id: number) {
  void router.replace({ query: { ...route.query, ticket: String(id) } })
}

function closeTicket() {
  const rest = { ...route.query }
  delete rest.ticket
  return router.replace({ query: rest })
}

// The panel hands focus back to the row button that opened it as it goes, but
// only when that button is still in the page. Often it is not: a quiet
// refresh after the agent assigned or resolved the ticket drops its row from
// an Unassigned or status filter, and a panel opened from a pasted link or an
// audit link had no opener here at all. By the tick after the panel has gone,
// its own hand-back has happened or has not.
async function onPanelClose() {
  await closeTicket()
  await nextTick()
  catchDroppedFocus()
}

// A delete can finish after the panel that started it is gone: Back takes
// `?ticket=` away while the request is still in flight, and the agent may have
// opened another ticket by the time it lands. Closing unconditionally would
// shut that other ticket's panel, so only the ticket that was deleted closes.
// The row is forgotten and the queue reloaded either way.
//
// Here the panel hands focus back while the deleted ticket's row is still on
// screen, and the refresh then removes that row, button and all. So the
// catch waits for the refresh.
async function onDeleted(id: number) {
  q.forgetTicket(id)
  if (openTicketId.value === id) void closeTicket()
  await q.refresh()
  await nextTick()
  catchDroppedFocus()
}

// A batch that went through takes the bulk bar away, and the Assign button
// that had focus with it.
async function assignSelected(assigneeId: number | null) {
  if (!(await q.assignSelected(assigneeId))) return
  await nextTick()
  catchDroppedFocus()
}

// Spread, not the card's filter on its own: applyFilters replaces the whole
// filter state, so passing it alone would silently clear whatever region or
// status the agent had already narrowed to. (The server keeps resolved
// tickets out of the Unassigned bucket even with a region, category or
// priority beside it, so the card and its list still agree.)
function showCard(filter: TicketFilters) {
  q.applyFilters({ ...q.filters.value, ...filter })
}

const listsDownSentence = computed(() => {
  const down = q.listsDown.value
  const lists = `The ${down.join(' and ')} list${down.length > 1 ? 's' : ''} could not be loaded.`
  const assignToo = q.assigneesFailed.value ? ', and so are the assign controls on this page' : ''
  return `${lists} The filters above are missing those choices${assignToo}. Reload to try again.`
})

const rejectedSentence = computed(() => {
  const rejected = q.bulkRejected.value
  if (!rejected) return ''
  const toThePool = rejected.assigneeId === null
  const what = toThePool
    ? 'Could not hand the selected tickets back to the pool. Nothing was changed.'
    : 'Could not assign the selected tickets. Nothing was changed.'
  // The refusal's own words when it has some for the agent (the session
  // changed hands, their own access was withdrawn): the advice below is
  // wrong for those, because pressing again is not what fixes them.
  if (rejected.reason) return `${what} ${rejected.reason}`
  // Nobody was picked when the batch went back to the pool, so the advice
  // below is about a person who does not exist and reads as a second,
  // unrelated fault.
  return toThePool
    ? `${what} Try again.`
    : `${what} Check that the person you picked can still work the queue, then try again.`
})

// The tickets that went, and to whom, in one short sentence. The ones that
// failed are the partial-failure line's business; when none went, that line
// says everything and this one stays quiet.
const assignedSentence = computed(() => {
  const result = q.bulkResult.value
  if (!result) return ''
  const done = result.results.filter((r) => r.ok).length
  if (done === 0) return ''
  const tickets = `${done} ticket${done === 1 ? '' : 's'}`
  const to = q.bulkAssigneeId.value
  if (to === null) return `${tickets} handed back to the pool.`
  const person = q.assignees.value.find((p) => p.id === to)
  return person ? `${tickets} assigned to ${person.name}.` : `${tickets} assigned.`
})

const partialFailureSentence = computed(() => {
  const failures = q.bulkFailures.value
  const total = q.bulkResult.value?.results.length ?? 0
  const named = failures.map((f) => describeFailure(f, q.numbersSeen)).join('; ')
  // Only when every failure is the deleted-row branch. bulk_assign fails two
  // ways: a row that is gone reads "not found", and anything the write itself
  // throws comes back as the exception text. That second kind can come good
  // on a second try, so this page must not tell the agent one is pointless.
  const allGone = failures.every((f) => f.error === 'not found')
  return (
    `${failures.length} of ${total} could not be assigned: ${named}.` +
    (allGone
      ? ' Tickets deleted while they sat in the selection come back as not found, and sending the batch again will not change that.'
      : '')
  )
})
</script>

<style scoped>
.ticket-queue {
  --ticket-queue-muted: #616970;
  --ticket-queue-danger: #a71d2a;

  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* The ground here is .content-area's --bg-light. --text-muted and --danger
   are 4.45:1 and 4.30:1 on it, both under AA; #616970 is 5.29:1 and #a71d2a
   6.98:1 (TicketDetailPage.vue measured the same pair). Dark gives both back
   to the theme: 6.19:1 and 6.58:1 on the dark ground. */
:root[data-theme='dark'] .ticket-queue {
  --ticket-queue-muted: var(--text-muted);
  --ticket-queue-danger: var(--danger);
}

/* The global focus ring is --dark-green, which the dark theme does not
   redefine: 2.79:1 on the dark card, and less on the row and bulk-bar
   washes, under the 3:1 a focus indicator needs. Every control on the page,
   the queue components' own included (hence :deep), takes the mint the
   audit, analytics and detail panel rings use: 6.13:1 on the card. The
   panel is teleported out of this element and keeps its own rule. Checked
   by queueContrast.spec.ts. */
:root[data-theme='dark'] .ticket-queue :deep(:focus-visible) {
  outline-color: var(--mint-green);
}

.ticket-queue__title {
  margin: 0 0 0.25rem;
  font-size: 1.75rem;
}

.ticket-queue__subtitle {
  margin: 0;
  color: var(--ticket-queue-muted);
  font-weight: 400;
}

.ticket-queue__toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

/* .btn-outline is green text on the page ground (5.72:1). The theme does not
   redefine --dark-green, which is 3.02:1 on the dark ground, so dark takes
   the mint the theme leaves alone (6.63:1). */
:root[data-theme='dark'] .ticket-queue__export,
:root[data-theme='dark'] .ticket-queue__export:hover {
  color: var(--mint-green);
}

/* main.css dims a .btn and drops its hover only for :disabled. The same
   look for the marked button, which stays focusable. */
.ticket-queue__export[aria-disabled='true'],
.ticket-queue__export[aria-disabled='true']:hover {
  opacity: 0.55;
  cursor: not-allowed;
  background-color: transparent;
  border-color: var(--border-light);
  transform: none;
  box-shadow: none;
}

.ticket-queue__alert {
  margin: 0;
  color: var(--ticket-queue-danger);
  font-size: 0.9rem;
  font-weight: 600;
}
</style>
