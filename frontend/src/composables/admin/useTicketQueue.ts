/**
 * State and actions of the support agent's ticket queue
 * (views/admin/tickets/TicketQueuePage.vue). Ported from adminweb's
 * TicketQueuePage.tsx plus the React Query hooks it used
 * (adminweb/src/query/ticket.ts).
 *
 * There is no query cache on this side, so the things the hooks did beyond
 * fetching are written out here (see the header of utils/ticketAgentAPI.ts):
 *   - the queue and the counters refetch when the tab becomes visible again,
 *     and nothing else on the page does;
 *   - every ticket write reloads the queue and the counters, on the page and
 *     walk already on screen;
 *   - every load carries a token, so an older answer arriving last cannot
 *     paint over a newer one.
 */
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'

import { ApiError, logApiError } from '@/utils/apiError'
import {
  bulkAssignTickets,
  exportTickets,
  fetchAssignees,
  fetchTicketQueue,
  fetchTicketRegions,
  fetchTicketSummary,
  saveTicketExport,
  ticketRefusalReason,
  wasRefused,
  type QueueWalk
} from '@/utils/ticketAgentAPI'
import type {
  AssigneeOption,
  BulkAssignResult,
  RegionOption,
  TicketFilters,
  TicketQueue,
  TicketSummary
} from '@/utils/ticketAgentSchema'
import { DEFAULT_PAGE_SIZE, servedPageCount } from '@/components/admin/tickets/queue/queueRules'

/** A batch the server refused outright (a 4xx, a dropped connection). Kept
 *  with what it asked for, because the sentence depends on it. */
export type RejectedBatch = {
  assigneeId: number | null
  /** The refusal in words written for a person, when there are some (see
   *  batchRefusalReason). The standing advice, "check the person you picked"
   *  or "try again", is wrong for every one of them. */
  reason?: string
}

/** Why a refused batch was refused, when the refusal says so in words meant
 *  for the agent, and the standing sentence would point them the wrong way.
 *
 *  Passed on: the transport's own refusals (the session changed hands, no
 *  secure session could be set up), where the next press is refused the same
 *  way, and the server's permission refusal ("You do not have support
 *  privileges."), where the fault is the agent's own access, not the person
 *  they picked. React showed neither (U2 GAP-06).
 *
 *  Held back: a refused assignee (code does_not_exist). The server's sentence
 *  names them by internal id, 'Cannot assign to user "18". ...', and an agent
 *  has never seen one of those; the standing sentence says the same thing by
 *  the person they picked. */
function batchRefusalReason(error: unknown): string | undefined {
  if (error instanceof ApiError && error.code === 'does_not_exist') return undefined
  return ticketRefusalReason(error)
}

// The response names a failure by internal id, and an agent has never seen
// one of those. The ticket number is what is on the row, in the search box and
// in the ticket itself, so that is what a failure has to be reported as.
export function describeFailure(
  failure: { ticketId: number; error?: string },
  numbers: Map<number, string>
): string {
  const name = numbers.get(failure.ticketId) ?? `ticket ${failure.ticketId}`
  // `||`, not `??`: the reason is an optional string, so an exception with no
  // message reaches us as "" rather than as nothing, and "SUP-2026-00001 ()"
  // reads as a bug in this page.
  return `${name} (${failure.error || 'no reason given'})`
}

export function useTicketQueue() {
  const page = ref(1)
  const limit = ref(DEFAULT_PAGE_SIZE)
  const filters = ref<TicketFilters>({})
  const selectedIds = ref<number[]>([])

  // Where each page of the current walk starts.
  //
  // The queue is ordered by last support activity, so its order moves while
  // somebody reads it. Paging by offset over that loses tickets: measured, an
  // internal note on three of two hundred, and those three appeared on no
  // page while the footer still said "20 of 20". So Next carries the snapshot
  // the walk began under plus the sort key of the last row served, and the
  // server returns the rows strictly after that place. Nothing in front of the
  // reader can push a row behind them.
  //
  // A plain Map rather than reactive state: writing it must not re-render,
  // and nothing on screen reads it directly. What the screen needs from it
  // (whether the page on screen continued a walk) is recorded with each
  // answer below, as `continuesWalk`.
  const walks = new Map<number, QueueWalk>()

  const queue = shallowRef<TicketQueue | null>(null)
  // True while a page with nothing yet to show is being read: first load,
  // and every page, size or filter change. A refresh of the page on screen
  // (tab focus, a write) keeps its rows and is not "loading".
  const queueLoading = ref(false)
  const queueFailed = ref(false)
  // Whether the queue is failing because it was refused (a 403) rather than
  // because of a fault. Reporting a refusal as "could not be loaded" tells
  // the agent the product is broken when it is doing what it should: their
  // queue access was taken away while the page was open (U2 GAP-04; the
  // audit and analytics pages already tell the two apart).
  const lastFailureRefused = ref(false)
  const queueRefused = computed(() => queueFailed.value && lastFailureRefused.value)
  // Whether the page on screen was read by continuing a walk (Next) rather
  // than fresh (page one, Previous, a page number, a new filter or size).
  const continuesWalk = ref(false)
  let queueToken = 0

  const summary = shallowRef<TicketSummary | null>(null)
  const summaryLoading = ref(false)
  const summaryFailed = ref(false)
  let summaryToken = 0

  const assignees = shallowRef<AssigneeOption[]>([])
  const assigneesPending = ref(true)
  const assigneesFailed = ref(false)
  const regions = shallowRef<RegionOption[]>([])
  const regionsFailed = ref(false)

  const bulkPending = ref(false)
  const bulkRejected = shallowRef<RejectedBatch | null>(null)
  const bulkResult = shallowRef<BulkAssignResult | null>(null)

  const exporting = ref(false)
  const exportError = ref('')

  // Ticket numbers outlive the rows they came from. A partial bulk assign has
  // to name the tickets it could not do, and those are precisely the ones
  // that have just left the queue, so by then there is no row to read a
  // number off. Every row served this visit is written in as it arrives.
  const numbersSeen = new Map<number, string>()

  const tickets = computed(() => queue.value?.items ?? [])

  const totalPages = computed(() => servedPageCount(page.value, limit.value, queue.value))

  const bulkFailures = computed(() => (bulkResult.value?.results ?? []).filter((r) => !r.ok))

  // Which list is down, in the order they are named. Saying both when only
  // one failed sends the agent hunting for a fault that is not there, and
  // only the assignee list feeds the assign controls.
  const listsDown = computed(() =>
    [assigneesFailed.value && 'assignee', regionsFailed.value && 'region'].filter(
      (name): name is string => Boolean(name)
    )
  )

  async function loadQueue(options: { refresh?: boolean } = {}) {
    const token = ++queueToken
    const requested = page.value
    // Page one has nothing in front of it, and a page reached by clicking its
    // number in the footer is the agent choosing to skip; neither continues a
    // walk, so both are answered live. Only a page Next reached has an entry.
    const walk = walks.get(requested)
    if (!options.refresh) {
      queue.value = null
      queueFailed.value = false
      queueLoading.value = true
    }
    try {
      const data = await fetchTicketQueue(requested, limit.value, filters.value, walk)
      if (token !== queueToken) return
      queue.value = data
      queueFailed.value = false
      continuesWalk.value = walk !== undefined
      data.items.forEach((ticket) => numbersSeen.set(ticket.id, ticket.ticketNumber))
      // Each page hands the next one its starting place.
      if (data.after) walks.set(requested + 1, { asOf: data.asOf, after: data.after })
    } catch (error) {
      if (token !== queueToken) return
      logApiError('Ticket queue', error)
      // A failed refresh keeps the rows already on screen; the page banner
      // says they may be stale.
      queueFailed.value = true
      lastFailureRefused.value = wasRefused(error)
    } finally {
      if (token === queueToken) queueLoading.value = false
    }
  }

  async function loadSummary() {
    const token = ++summaryToken
    summaryLoading.value = summary.value === null
    try {
      const data = await fetchTicketSummary()
      if (token !== summaryToken) return
      summary.value = data
      summaryFailed.value = false
    } catch (error) {
      if (token !== summaryToken) return
      logApiError('Ticket counters', error)
      summaryFailed.value = true
    } finally {
      if (token === summaryToken) summaryLoading.value = false
    }
  }

  // Once per visit, like the React hooks: nothing on this page refetches the
  // two option lists. The detail panel fetches its own roster every time it
  // opens (T02), so a grant or revoke on the roster is never stale there.
  async function loadOptionLists() {
    assigneesPending.value = true
    await Promise.all([
      fetchAssignees()
        .then((people) => {
          assignees.value = people
          assigneesFailed.value = false
        })
        .catch((error) => {
          logApiError('Ticket assignee list', error)
          assignees.value = []
          assigneesFailed.value = true
        })
        .finally(() => {
          assigneesPending.value = false
        }),
      fetchTicketRegions()
        .then((options) => {
          regions.value = options
          regionsFailed.value = false
        })
        .catch((error) => {
          logApiError('Ticket region list', error)
          regions.value = []
          regionsFailed.value = true
        })
    ])
  }

  // Anything that changes what is being walked starts a new walk.
  function restartWalk() {
    walks.clear()
  }

  function goToPage(next: number) {
    // Only stepping one page forward continues the walk. Everything else,
    // Previous included, is a jump, and a jump reads from a fresh snapshot.
    // Keeping the old cursors across a jump would mix two walks and show
    // pages from different moments as if they were one.
    //
    // Previous therefore re-reads by offset, and a row worked while the
    // reader was ahead of it can come back a second time on the way down.
    // That is visible and harmless: no row is lost either way, which is the
    // property the snapshot exists to hold.
    //
    // Reaching page N-1 with the forward cursor page N-2 handed out was tried
    // and reverted. It does not remove the repeats, it moves them: measured
    // against the queue endpoint, 220 tickets ten to a page with three worked
    // behind the reader, the cursor route repeated six rows across pages
    // where the offset route repeated three. Rows leaving the snapshot shrink
    // it, so an old cursor pulls the following page's rows up into the gap.
    // Do not restore it without measuring both routes. (The backend's
    // services/paging.py docstring still suggests that route; follow this.)
    if (next !== page.value + 1) restartWalk()
    page.value = next
    void loadQueue()
  }

  function applyFilters(next: TicketFilters) {
    filters.value = next
    // Page 3 of the old filter is rarely page 3 of the new one.
    restartWalk()
    page.value = 1
    selectedIds.value = []
    void loadQueue()
  }

  function setPageSize(size: number) {
    limit.value = size
    restartWalk()
    page.value = 1
    // The selection is kept, as it was in React: a size change shows the
    // same queue cut differently, while a filter change shows another one.
    void loadQueue()
  }

  function toggle(id: number) {
    selectedIds.value = selectedIds.value.includes(id)
      ? selectedIds.value.filter((x) => x !== id)
      : [...selectedIds.value, id]
  }

  // Scoped to the rows on screen. The selection deliberately survives paging,
  // so comparing its total length against this page's row count made the
  // header checkbox answer a question nobody asked: with 10 selected on page
  // one it showed page two as fully selected, and clicking it cleared the
  // other page's selection instead of selecting this one.
  function toggleAll() {
    const pageIds = tickets.value.map((t) => t.id)
    const current = selectedIds.value
    const allOnPage = pageIds.length > 0 && pageIds.every((id) => current.includes(id))
    selectedIds.value = allOnPage
      ? current.filter((id) => !pageIds.includes(id))
      : [...new Set([...current, ...pageIds])]
  }

  // The bar's Clear. The rejected-batch message goes with the selection (the
  // watch below); the last batch's partial-failure message goes here too, as
  // React's reset() took both, or the next selection opens showing the last
  // one's failure.
  function clearSelection() {
    selectedIds.value = []
    bulkResult.value = null
  }

  // Drop it from the selection too. The bulk bar counts selectedIds, so
  // leaving it there makes the bar offer to assign a ticket that no longer
  // exists.
  function forgetTicket(id: number) {
    selectedIds.value = selectedIds.value.filter((x) => x !== id)
  }

  // A rejected batch is described inside the selection block, because the
  // selection is still there when a request is refused. Whenever the
  // selection empties, by the bar's Clear or any other road (a filter change,
  // a card, the last selected ticket deleted from the panel), the message
  // goes with it: otherwise the next selection opens reading as though it had
  // failed too, before anything was sent. React reset it on Clear only, so a
  // filter change left it waiting for the next batch.
  watch(
    () => selectedIds.value.length,
    (count) => {
      if (count === 0) bulkRejected.value = null
    }
  )

  // Anything that changes a ticket reloads the queue and the counters: a
  // status change moves it between counter cards and can move it in the sort
  // order. The page on screen is re-read under the walk it was read with, so
  // on page two and beyond a ticket just worked leaves that page.
  function refresh() {
    void loadQueue({ refresh: true })
    void loadSummary()
  }

  // null hands the batch back to the pool, which the endpoint has always
  // accepted. One request for the whole batch: the endpoint answers per
  // ticket, so a partly failed batch is still a 200.
  async function assignSelected(assigneeId: number | null) {
    // Reads live state, not a rendered prop: two clicks in one tick must
    // still send one batch.
    if (bulkPending.value || selectedIds.value.length === 0) return
    const ticketIds = [...selectedIds.value]
    bulkPending.value = true
    bulkRejected.value = null
    bulkResult.value = null
    try {
      const result = await bulkAssignTickets(ticketIds, assigneeId)
      bulkResult.value = result
      // The whole selection goes, failed rows included. The partial-failure
      // message, outside the selection block, is what names the ones to redo.
      selectedIds.value = []
      refresh()
    } catch (error) {
      logApiError('Ticket bulk assign', error)
      bulkRejected.value = { assigneeId, reason: batchRefusalReason(error) }
    } finally {
      bulkPending.value = false
    }
  }

  /** Client item C-09: the tickets the current filters match, as a
   *  spreadsheet. Only the filters travel; the page, the size and the walk
   *  stay here, because an export is a fresh look at everything that
   *  matches now. */
  async function exportQueue() {
    if (exporting.value) return
    exporting.value = true
    exportError.value = ''
    try {
      saveTicketExport(await exportTickets({ ...filters.value }))
    } catch (error) {
      logApiError('Ticket export', error)
      exportError.value =
        ticketRefusalReason(error) ?? 'Could not export the tickets. Please try again.'
    } finally {
      exporting.value = false
    }
  }

  // React Query's refetchOnWindowFocus, which the React queue and counters
  // turned on and nothing else on the page did. In the installed
  // @tanstack/query-core (5.100.9, focusManager.js) that option listens for
  // `visibilitychange` alone and refetches when the tab is visible again, so
  // this does the same: an agent works with the queue open and comes back to
  // it expecting to see what arrived while they were away. No polling.
  function onVisibilityChange() {
    if (document.visibilityState === 'hidden') return
    // A page that is still being read for the first time is already fresh.
    if (queueLoading.value) {
      void loadSummary()
      return
    }
    refresh()
  }

  onMounted(() => {
    // Fetched on every entry. React showed its cached rows and counters on a
    // return visit without asking the server (U2 GAP-03); there is no cache
    // here, and a queue that is minutes old on arrival is the wrong default.
    void loadQueue()
    void loadSummary()
    void loadOptionLists()
    document.addEventListener('visibilitychange', onVisibilityChange)
  })

  onBeforeUnmount(() => {
    document.removeEventListener('visibilitychange', onVisibilityChange)
    // Anything still in flight answers into nothing.
    queueToken++
    summaryToken++
  })

  return {
    page,
    limit,
    filters,
    selectedIds,
    queue,
    tickets,
    queueLoading,
    queueFailed,
    queueRefused,
    continuesWalk,
    totalPages,
    summary,
    summaryLoading,
    summaryFailed,
    assignees,
    assigneesPending,
    assigneesFailed,
    regions,
    regionsFailed,
    listsDown,
    bulkPending,
    bulkRejected,
    bulkResult,
    bulkFailures,
    numbersSeen,
    exporting,
    exportError,
    goToPage,
    applyFilters,
    setPageSize,
    toggle,
    toggleAll,
    clearSelection,
    forgetTicket,
    assignSelected,
    exportQueue,
    refresh
  }
}
