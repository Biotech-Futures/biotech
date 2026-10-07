<template>
  <Teleport to="body">
    <div class="ticket-panel">
      <!-- Clicking beside the panel closes it, as the React sheet's overlay
           did. Hidden from assistive tech: Esc and the Close button are the
           ways out for everybody else. -->
      <div class="ticket-panel__backdrop" aria-hidden="true" @mousedown.self="close"></div>

      <!-- tabindex="-1": focus lands here when the panel opens, so the dialog
           is announced by its name, and a click on plain text inside it keeps
           focus inside rather than dropping it to the page behind. -->
      <section
        ref="sheet"
        class="ticket-panel__sheet"
        role="dialog"
        aria-modal="true"
        tabindex="-1"
        :aria-labelledby="ticket ? titleId : undefined"
        :aria-label="ticket ? undefined : 'Ticket detail'"
        @keydown="trapTab"
      >
        <header class="ticket-panel__header">
          <div v-if="ticket" class="ticket-panel__heading">
            <h2 :id="titleId" class="ticket-panel__title">
              <span>{{ ticket.ticketNumber }}</span>
              <TicketStatusBadge :status="ticket.status" />
              <TicketPriorityBadge :priority="ticket.priority" />
              <!-- Computed by the server, not derived here. The queue row's
                   own badge, so the two read the same. -->
              <OverdueBadge v-if="ticket.overdue" class="ticket-panel__overdue" />
            </h2>
            <p class="ticket-panel__subject">{{ ticket.subject }}</p>
          </div>
          <button type="button" class="ticket-panel__close" aria-label="Close" @click="close">
            <TicketIcon name="x" :size="18" />
          </button>
        </header>

        <div class="ticket-panel__body">
          <p v-if="!ticket && loadState === 'loading'" class="ticket-panel__quiet">Loading…</p>
          <!-- Never a permanent spinner. The commonest way to land here is a
               link to a ticket that has since been deleted, and "Loading…"
               forever reads as a broken page rather than an answer.

               T28 does not carry over: the React sheet flashed this line on
               every close, because its ticket went null while the sheet
               animated out. Here the queue unmounts the panel on close, so
               there is no state in which it can show. -->
          <p v-else-if="!ticket" class="ticket-panel__error" role="alert">
            That ticket could not be opened. It may have been deleted.
          </p>

          <template v-else>
            <!-- The four controls are driven by the server's copy of the
                 ticket, so a rejected PATCH leaves them showing the old value
                 with no other sign. The agent watches the dropdown snap back
                 and has no way to tell that from having misclicked. -->
            <p v-if="updateError" class="ticket-panel__error" role="alert">{{ updateError }}</p>

            <!-- The assignee request is this panel's own, so its failure is
                 said here. In React the queue page made the request and its
                 banner said it; here nothing else on screen would, and the
                 only sign left would be the disabled row inside the dropdown.
                 The row stays too: it is what explains a short list to
                 somebody who has opened the dropdown. -->
            <div v-if="assigneeState === 'failed'" class="ticket-panel__assignees-failed">
              <p :id="`${idBase}-assignees-failed`" class="ticket-panel__error" role="alert">
                The assignee list could not be loaded. The Assignee control is missing those
                choices.
              </p>
              <button
                type="button"
                class="ticket-panel__retry"
                :aria-describedby="`${idBase}-assignees-failed`"
                @click="retryAssignees"
              >
                Try again
              </button>
            </div>

            <TicketTriageControls
              :key="`triage-${ticket.id}`"
              :ticket="ticket"
              :assignees="assignees"
              :assignees-unavailable="assigneeState !== 'ready'"
              :apply="applyPatch"
            />

            <div class="ticket-panel__tabs" role="tablist" aria-label="Ticket sections">
              <button
                v-for="item in TABS"
                :id="`${idBase}-tab-${item.key}`"
                :key="item.key"
                :ref="(el) => (tabButtons[item.key] = el as HTMLButtonElement | null)"
                type="button"
                role="tab"
                class="ticket-panel__tab"
                :class="{ 'ticket-panel__tab--active': tab === item.key }"
                :aria-selected="tab === item.key"
                :aria-controls="`${idBase}-panel-${item.key}`"
                :tabindex="tab === item.key ? 0 : -1"
                @click="selectTab(item.key)"
                @keydown="onTabKeydown"
              >
                {{ item.label }}
              </button>
            </div>

            <!-- v-show, not v-if (T09). The React panel unmounted both message
                 boxes when Details was opened, and a half-written reply and
                 note went with them without a word. -->
            <div
              v-show="tab === 'conversation'"
              :id="`${idBase}-panel-conversation`"
              role="tabpanel"
              class="ticket-panel__tabpanel"
              :aria-labelledby="`${idBase}-tab-conversation`"
            >
              <TicketMessageTimeline
                :key="`timeline-${ticket.id}`"
                :ticket-id="ticket.id"
                :messages="ticket.messages"
              />
              <!-- Keyed by ticket, so a draft typed for one ticket can never
                   end up under another (the React boxes were not keyed and
                   could carry a draft across on Back/Forward). A refetch of
                   the same ticket keeps the key, and so keeps the draft. -->
              <TicketReplyComposer :key="`reply-${ticket.id}`" :send="sendReply" />
              <TicketNoteComposer :key="`note-${ticket.id}`" :send="sendNote" />
            </div>

            <div
              v-show="tab === 'details'"
              :id="`${idBase}-panel-details`"
              role="tabpanel"
              class="ticket-panel__tabpanel"
              :aria-labelledby="`${idBase}-tab-details`"
            >
              <TicketFacts :ticket="ticket" />
              <TicketHistoryList :entries="history" :state="historyState" @retry="retryHistory" />

              <!-- Only admins may delete (DEC-024), so the control is not
                   rendered at all for a support agent. The server refuses
                   them either way (IsAdminScoped). -->
              <section v-if="canDelete" class="ticket-panel__delete" :aria-labelledby="`${idBase}-delete`">
                <h3 :id="`${idBase}-delete`" class="ticket-panel__delete-title">Delete this ticket</h3>
                <p class="ticket-panel__delete-hint">
                  For a duplicate, a test submission or spam. It leaves the queue and the requester's
                  own list, and there is no undo. To close a real enquiry, mark it Resolved instead.
                </p>
                <button
                  ref="deleteButton"
                  type="button"
                  class="ticket-panel__delete-button"
                  :disabled="deleting"
                  @click="confirmOpen = true"
                >
                  {{ deleting ? 'Deleting…' : 'Delete ticket' }}
                </button>
                <p v-if="deleteError" class="ticket-panel__error" role="alert">{{ deleteError }}</p>
              </section>
            </div>
          </template>
        </div>
      </section>

      <ConfirmDialog
        v-if="ticket && canDelete"
        v-model="confirmOpen"
        :title="confirmTitle"
        :message="deleteMessage"
        confirm-label="Delete"
        cancel-label="Keep it"
        busy-label="Deleting…"
        variant="danger"
        :busy="deleting"
        @confirm="confirmDelete"
      />
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from 'vue'

import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import OverdueBadge from '@/components/admin/tickets/queue/OverdueBadge.vue'
import TicketIcon from '@/components/support/TicketIcon.vue'
import TicketPriorityBadge from '@/components/support/TicketPriorityBadge.vue'
import TicketStatusBadge from '@/components/support/TicketStatusBadge.vue'
import { logApiError } from '@/utils/apiError'
import {
  deleteTicket,
  fetchAssignees,
  fetchTicketDetail,
  fetchTicketHistory,
  sendTicketMessage,
  updateTicket,
  type TicketPatch
} from '@/utils/ticketAgentAPI'
import type {
  AssigneeOption,
  TicketDetail,
  TicketHistoryEntry
} from '@/utils/ticketAgentSchema'

import TicketFacts from './TicketFacts.vue'
import TicketHistoryList from './TicketHistoryList.vue'
import TicketMessageTimeline from './TicketMessageTimeline.vue'
import TicketNoteComposer from './TicketNoteComposer.vue'
import TicketReplyComposer from './TicketReplyComposer.vue'
import TicketTriageControls from './TicketTriageControls.vue'
import { changeNotSavedMessage, deleteRefusedMessage } from './ticketDetailText'

// The contract with the queue page (fixed by the scaffold's placeholder):
//
// ticketId  - the ticket to show; the panel loads its own data. The queue
//             mounts the panel while a ticket is open and unmounts it on
//             close, so mounting is opening.
// canDelete - the server's admin flag (auth.isTicketAdmin): only admins may
//             delete, the endpoint is IsAdminScoped.
// close     - the agent dismissed the panel.
// changed   - a write went through; the queue reloads rows and counters.
//             "A status change moves it between counter cards and can move it
//             in the sort order."
// deleted   - the ticket is gone; the queue closes the panel and reloads.
//             Sent instead of `changed`, not as well: the queue does both
//             things on this one event.
//
// onChanged and onDeleted below are not new inputs. They are the queue's own
// @changed and @deleted listeners, which Vue hands over as props named that
// way when they are declared (its emit() says an event must be "declared in
// the emits option" or "as an onX prop"). Declared so the panel can still
// reach them after it has been closed; see tellQueue below. The queue's
// template is unchanged: it still writes @changed and @deleted.
const props = defineProps<{
  ticketId: number
  canDelete: boolean
  onChanged?: () => void
  onDeleted?: (id: number) => void
}>()
const emit = defineEmits<{ close: []; changed: []; deleted: [id: number] }>()

type Tab = 'conversation' | 'details'
const TABS: { key: Tab; label: string }[] = [
  { key: 'conversation', label: 'Conversation' },
  { key: 'details', label: 'Details' }
]

const idBase = useId()
const titleId = `${idBase}-title`

const sheet = ref<HTMLElement | null>(null)
const deleteButton = ref<HTMLButtonElement | null>(null)
const tabButtons: Partial<Record<Tab, HTMLButtonElement | null>> = {}

// --- The ticket -----------------------------------------------------------------

const ticket = ref<TicketDetail | null>(null)
const loadState = ref<'loading' | 'ready' | 'failed'>('loading')

// Changing ticket twice in a row leaves two requests in flight, and the slower
// one must not paint over the newer one: that would put a ticket on screen the
// queue is not asking for. Every read takes a token, and every paint checks it
// and the id. A write's own answer bumps the token too, so a read that set off
// before the write cannot land after it and put the old values back.
let loadToken = 0

async function loadTicket(id: number, { quiet = false } = {}) {
  const token = ++loadToken
  if (!quiet) {
    ticket.value = null
    loadState.value = 'loading'
  }
  try {
    const result = await fetchTicketDetail(id)
    if (token !== loadToken || id !== props.ticketId) return
    ticket.value = result
    loadState.value = 'ready'
  } catch (error) {
    if (token !== loadToken || id !== props.ticketId) return
    logApiError('ticket detail', error)
    // A quiet reload that fails keeps what is on screen; the write it
    // followed has already said whether it worked.
    if (!quiet) loadState.value = 'failed'
  }
}

// --- Who the ticket can be handed to --------------------------------------------

// Read fresh every time a ticket is opened, never kept from an earlier open.
// A grant or revoke on the support agents page changes this list, and in the
// React app that change never reached the open dropdown (T02): a revoked agent
// stayed on offer until a full reload, and picking them was refused.
const assignees = ref<AssigneeOption[]>([])
const assigneeState = ref<'loading' | 'ready' | 'failed'>('loading')
let assigneeToken = 0

async function loadAssignees() {
  const token = ++assigneeToken
  assignees.value = []
  assigneeState.value = 'loading'
  try {
    const list = await fetchAssignees()
    if (token !== assigneeToken) return
    assignees.value = list
    assigneeState.value = 'ready'
  } catch (error) {
    if (token !== assigneeToken) return
    logApiError('ticket assignees', error)
    assigneeState.value = 'failed'
  }
}

// The Try again button goes away while the list loads, and focus must not go
// with it. It lands on the Assignee control, which is what the list is for:
// once the list is back that is where the agent picks from, and if it fails
// again the alert says so.
function retryAssignees() {
  void loadAssignees()
  void nextTick(() =>
    sheet.value?.querySelector<HTMLSelectElement>('select[aria-label="Change assignee"]')?.focus()
  )
}

// --- History (behind the Details tab) --------------------------------------------

const tab = ref<Tab>('conversation')
const history = ref<TicketHistoryEntry[] | null>(null)
const historyState = ref<'loading' | 'ready' | 'failed'>('loading')
let historyToken = 0

// Read each time Details is shown and after each write while it is, the way
// the React query refetched it: the list is only ever looked at there.
async function loadHistory(id: number) {
  const token = ++historyToken
  historyState.value = 'loading'
  try {
    const rows = await fetchTicketHistory(id)
    if (token !== historyToken || id !== props.ticketId) return
    history.value = rows
    historyState.value = 'ready'
  } catch (error) {
    if (token !== historyToken || id !== props.ticketId) return
    logApiError('ticket history', error)
    historyState.value = 'failed'
  }
}

function retryHistory() {
  void loadHistory(props.ticketId)
}

function selectTab(next: Tab) {
  tab.value = next
  if (next === 'details') void loadHistory(props.ticketId)
}

// Arrow keys move between the two tabs, as the WAI-ARIA tabs pattern expects:
// only the selected tab is in the Tab order.
function onTabKeydown(event: KeyboardEvent) {
  const order = TABS.map((item) => item.key)
  const at = order.indexOf(tab.value)
  let next: Tab | undefined
  if (event.key === 'ArrowRight') next = order[(at + 1) % order.length]
  else if (event.key === 'ArrowLeft') next = order[(at - 1 + order.length) % order.length]
  else if (event.key === 'Home') next = order[0]
  else if (event.key === 'End') next = order[order.length - 1]
  if (!next) return
  event.preventDefault()
  selectTab(next)
  void nextTick(() => tabButtons[next]?.focus())
}

// --- Writes ------------------------------------------------------------------------

const updateError = ref<string | null>(null)
const deleteError = ref<string | null>(null)

let writeSeq = 0
let paintedWriteSeq = 0
let writesInFlight = 0
let burstSucceeded = 0

// Set as the panel starts to go away. The queue unmounts it on close, and a
// write the agent made just before closing can still be on its way then.
let unmounted = false

/**
 * Tells the queue that a write went through, or that the ticket is gone.
 *
 * In React this was the query layer's job (useTicketInvalidation, run from
 * each mutation's onSuccess), and it happened whether or not the sheet was
 * still open. An emit cannot do that: Vue drops every emit from a component
 * that has been unmounted (runtime-core emit(): `if (instance.isUnmounted)
 * return`). So an agent who changed the status and pressed Esc before the
 * answer came back got the change on the server and a queue row and counters
 * that still showed the old status. Once the panel is going, the queue's own
 * listener is called directly instead.
 */
function tellQueue(event: 'changed'): void
function tellQueue(event: 'deleted', id: number): void
function tellQueue(event: 'changed' | 'deleted', id?: number) {
  if (!unmounted) {
    if (event === 'changed') emit('changed')
    else emit('deleted', id as number)
    return
  }
  // A throw here must not turn a write that went through into one that
  // reads as failed. emit() hands a listener's throw to Vue's error handler
  // for the same reason.
  try {
    if (event === 'changed') props.onChanged?.()
    else props.onDeleted?.(id as number)
  } catch (error) {
    console.error(`[TicketDetailPanel] the queue's ${event} listener threw`, error)
  }
}

/**
 * Every write this panel makes goes through here, so each one does the same
 * three things the React query layer did for it: tell the queue (it reloads
 * rows and counters), show the server's new copy of this ticket, and refresh
 * the history if it is on screen.
 *
 * The write's own answer carries the whole ticket, so it is painted directly
 * rather than read again. Two writes can be in flight at once (the controls
 * are not locked while one saves), and their answers can come back in either
 * order: only an answer newer than the last one painted is used, and when
 * more than one write landed in a row the ticket is read once more at the
 * end, because the server may have applied them in the other order.
 *
 * Once the panel has closed, only the first of the three still matters:
 * there is no screen left to paint, so nothing is read again either.
 */
async function write(id: number, run: () => Promise<TicketDetail>): Promise<TicketDetail> {
  const seq = ++writeSeq
  if (writesInFlight === 0) burstSucceeded = 0
  writesInFlight += 1
  try {
    const result = await run()
    burstSucceeded += 1
    tellQueue('changed')
    if (!unmounted && id === props.ticketId && seq > paintedWriteSeq) {
      paintedWriteSeq = seq
      loadToken += 1
      ticket.value = result
      loadState.value = 'ready'
    }
    return result
  } finally {
    writesInFlight -= 1
    if (!unmounted && writesInFlight === 0 && burstSucceeded > 0 && id === props.ticketId) {
      if (burstSucceeded > 1) await loadTicket(id, { quiet: true })
      if (tab.value === 'details') void loadHistory(id)
    }
  }
}

async function applyPatch(patch: TicketPatch): Promise<void> {
  const id = props.ticketId
  // A new attempt clears the old warning, as a new mutation did in React.
  updateError.value = null
  try {
    await write(id, () => updateTicket(id, patch))
  } catch (error) {
    logApiError('ticket update', error)
    if (id === props.ticketId) updateError.value = changeNotSavedMessage(error)
  }
}

// The boxes keep what was typed when a send fails, and they can only know it
// failed if the rejection reaches them, so these rethrow.
function sendReply(body: string, files: File[], moveToPending: boolean) {
  const id = props.ticketId
  // "Reply and wait for their reply" is ONE request. The backend moves the
  // ticket to pending_user inside the same lock, before the email is built,
  // so the email sees the status the agent intended.
  return write(id, () =>
    sendTicketMessage(id, { messageType: 'support_reply', body, files, moveToPending })
  )
}

function sendNote(body: string, files: File[]) {
  const id = props.ticketId
  // No moveToPending, ever: a note must not move the ticket, and the server
  // refuses the flag on one.
  return write(id, () => sendTicketMessage(id, { messageType: 'internal_note', body, files }))
}

// --- Delete (admins only) --------------------------------------------------------

const confirmOpen = ref(false)
const deleting = ref(false)

const deleteMessage = computed(() => {
  const whose = ticket.value?.requester ? `${ticket.value.requester.name}'s` : "the requester's"
  return (
    `This removes it from the queue and from ${whose} own list of enquiries. ` +
    'It cannot be undone from the app. A record of the deletion is kept in the history.'
  )
})

async function confirmDelete() {
  if (deleting.value) return
  const id = props.ticketId
  deleting.value = true
  deleteError.value = null
  try {
    await deleteTicket(id)
    confirmOpen.value = false
    tellQueue('deleted', id)
  } catch (error) {
    logApiError('ticket delete', error)
    confirmOpen.value = false
    if (id === props.ticketId) deleteError.value = deleteRefusedMessage(error)
  } finally {
    deleting.value = false
  }
}

const confirmTitle = computed(() => (ticket.value ? `Delete ${ticket.value.ticketNumber}?` : ''))

/** The confirmation's "Keep it" button. ConfirmDialog teleports to body and
 *  exposes no ref, so it is found by the title this panel gave it and the
 *  label this panel gave the button. */
function keepItButton(): HTMLButtonElement | null {
  for (const dialog of Array.from(document.querySelectorAll<HTMLElement>('[role="dialog"]'))) {
    if (dialog === sheet.value) continue
    if (dialog.querySelector('h2')?.textContent?.trim() !== confirmTitle.value) continue
    const buttons = Array.from(dialog.querySelectorAll<HTMLButtonElement>('button'))
    return buttons.find((button) => button.textContent?.trim() === 'Keep it') ?? null
  }
  return null
}

// The confirmation opens on "Keep it", as the React AlertDialog did (Radix
// focuses its Cancel). ConfirmDialog focuses its confirm button instead, one
// tick after it opens (ConfirmDialog.vue focusConfirm), and for this dialog
// that is the destructive one: an Enter pressed straight after opening would
// delete a ticket that cannot be restored. So focus is moved once that has
// happened: the first tick here resumes before ConfirmDialog's (both wait on
// the same render), the second after it.
//
// ConfirmDialog does not hand focus back when it closes either. The Delete
// button is where the agent was, and where the warning below it is.
watch(confirmOpen, async (open, wasOpen) => {
  if (open) {
    await nextTick()
    await nextTick()
    if (confirmOpen.value) keepItButton()?.focus()
    return
  }
  if (wasOpen) void nextTick(() => deleteButton.value?.focus())
})

// --- Moving between tickets ------------------------------------------------------

watch(
  () => props.ticketId,
  (id) => {
    // Warnings belong to the ticket they were about: a failure on one ticket
    // must not stay on screen while the agent looks at the next one. The
    // message boxes are keyed by ticket and reset themselves.
    updateError.value = null
    deleteError.value = null
    confirmOpen.value = false
    history.value = null
    historyState.value = 'loading'
    void loadTicket(id)
    void loadAssignees()
    if (tab.value === 'details') void loadHistory(id)
  },
  { immediate: true }
)

// --- Opening, closing and focus ------------------------------------------------------

function close() {
  emit('close')
}

// Whatever had focus when the panel was created is what opened it (the queue
// row's button, usually). It gets focus back when the panel goes away.
const opener =
  document.activeElement instanceof HTMLElement && document.activeElement !== document.body
    ? document.activeElement
    : null

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

function focusables(): HTMLElement[] {
  if (!sheet.value) return []
  return Array.from(sheet.value.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
    (el) =>
      // The hidden tab's controls are display:none through v-show, and the
      // unselected tab button is out of the Tab order on purpose.
      !el.closest('[style*="display: none"]') && el.getAttribute('tabindex') !== '-1'
  )
}

// Tab and Shift+Tab go round the panel rather than out of it to the page
// behind the backdrop.
function trapTab(event: KeyboardEvent) {
  if (event.key !== 'Tab') return
  const items = focusables()
  if (!items.length) return
  const first = items[0]
  const last = items[items.length - 1]
  const active = document.activeElement
  if (event.shiftKey && (active === first || active === sheet.value)) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && active === last) {
    event.preventDefault()
    first.focus()
  }
}

// Esc closes the panel from wherever focus is, as the React sheet did. Heard
// on the capture phase so it is seen before ConfirmDialog's own Esc handler
// closes that dialog: while the confirm is open, Esc belongs to it.
function onDocumentKeydown(event: KeyboardEvent) {
  if (event.key !== 'Escape' || confirmOpen.value) return
  // A triage control holding a value it has not sent yet takes this Esc for
  // itself, to put the saved value back (TicketTriageControls onKeydown), the
  // way an open Radix list in React took Esc before the sheet did. The next
  // Esc closes the panel.
  if (event.target instanceof Element && event.target.closest('[data-unsaved-choice]')) return
  close()
}

// Focus that escapes to the page behind (a mouse click out there is stopped
// by the backdrop, but a script or the browser can still move it) is brought
// back. The confirm dialog is its own modal on top and keeps its focus.
function onDocumentFocusIn(event: FocusEvent) {
  const target = event.target as Node | null
  if (!sheet.value || !target || confirmOpen.value) return
  if (sheet.value.contains(target)) return
  sheet.value.focus()
}

onMounted(() => {
  document.addEventListener('keydown', onDocumentKeydown, true)
  document.addEventListener('focusin', onDocumentFocusIn)
  void nextTick(() => sheet.value?.focus())
})

onBeforeUnmount(() => {
  unmounted = true
  document.removeEventListener('keydown', onDocumentKeydown, true)
  document.removeEventListener('focusin', onDocumentFocusIn)
  if (opener && opener.isConnected) opener.focus()
})
</script>

<style scoped>
/* Same frame as FormSheet.vue (right-hand drawer over a backdrop, z-index
   1999 so ConfirmDialog's 2000 stacks on top), with the focus handling
   FormSheet lacks. Full width on a phone, 42rem at most, as the React sheet.
   The first redesign round (October 2026) gives it the ticket screens' greys
   and rules, a little more room at the sides, and the card colour as its
   dark ground.

   Contrast, measured with the WCAG formula on the panel's ground (--white in
   light, #1d2826 in dark):
     light  muted #5a6268 6.21   error #a71d2a 7.36
            delete button #fff on #b3202c 6.65   control edge #84938f 3.21
            active tab rule #017151 6.03 (non-text, needs 3:1)
     dark   muted #a3b3ae 6.95   error --danger 5.49   control edge #70827d 3.74
            active tab rule #5ea99e 5.52   focus ring #5ea99e 5.52
   --dark-green is not redefined for dark and is 2.52:1 there (U1 5.3), so
   the dark rule and the focus ring take the mint literal instead. The
   designer drew his dark tab rule in brand green; the mint stays, because
   his would not reach 3:1. color-scheme has the browser draw the composer's
   checkbox dark, as his dark panel shows it. */
.ticket-panel {
  --panel-muted: #5a6268;
  --panel-danger: #a71d2a;
  --panel-accent: #017151;
  --panel-ground: var(--white);
  --panel-rule: #e6eae8;
  --panel-edge: #84938f;
  --panel-danger-ground: #fdf0f0;

  position: fixed;
  inset: 0;
  z-index: 1999;
}

:root[data-theme='dark'] .ticket-panel {
  --panel-muted: #a3b3ae;
  --panel-danger: var(--danger);
  --panel-accent: #5ea99e;
  --panel-ground: #1d2826;
  --panel-rule: #2b3936;
  --panel-edge: #70827d;
  --panel-danger-ground: #3a1d20;

  color-scheme: dark;
}

.ticket-panel__backdrop {
  position: absolute;
  inset: 0;
  background-color: rgba(0, 0, 0, 0.4);
}

.ticket-panel__sheet {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  width: min(100vw, 42rem);
  background-color: var(--panel-ground);
  color: var(--charcoal);
  box-shadow: -24px 0 60px rgba(7, 17, 15, 0.18);
  animation: ticket-panel-in 0.22s ease;
}

.ticket-panel__sheet:focus {
  outline: none;
}

.ticket-panel :focus-visible {
  outline: 2px solid var(--panel-accent);
  outline-offset: 2px;
}

.ticket-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.125rem 1.5rem;
  border-bottom: 1px solid var(--panel-rule);
}

.ticket-panel__heading {
  min-width: 0;
}

/* The badges sit a little further from the number than from each other. */
.ticket-panel__title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.625rem;
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  line-height: 1.3;
}

.ticket-panel__title > span:first-child {
  margin-right: 0.2rem;
}

.ticket-panel__subject {
  margin: 0.25rem 0 0;
  font-size: 0.95rem;
  font-weight: 500;
  line-height: 1.4;
  overflow-wrap: anywhere;
}

.ticket-panel__close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  padding: 0;
  border: 1px solid var(--panel-edge);
  border-radius: 8px;
  background-color: var(--panel-ground);
  color: var(--charcoal);
  cursor: pointer;
}

.ticket-panel__body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1rem 1.5rem 1.5rem;
}

.ticket-panel__quiet {
  margin: 0;
  font-size: 0.9rem;
  color: var(--panel-muted);
}

.ticket-panel__error {
  margin: 0;
  font-size: 0.88rem;
  color: var(--panel-danger);
}

.ticket-panel__assignees-failed {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.6rem;
}

/* The same quiet button as the History list's Try again. */
.ticket-panel__retry {
  padding: 0.3rem 0.8rem;
  border: 1px solid var(--panel-edge);
  border-radius: 8px;
  background: var(--panel-ground);
  color: var(--charcoal);
  font-family: inherit;
  font-size: 0.82rem;
  cursor: pointer;
}

/* Both tabs bold; the chosen one darker and underlined in the accent. */
.ticket-panel__tabs {
  display: flex;
  gap: 0.25rem;
  border-bottom: 1px solid var(--panel-rule);
}

.ticket-panel__tab {
  margin-bottom: -1px;
  padding: 0.75rem 0.875rem;
  border: none;
  border-bottom: 3px solid transparent;
  background: none;
  color: var(--panel-muted);
  font-family: inherit;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
}

.ticket-panel__tab--active {
  border-bottom-color: var(--panel-accent);
  color: var(--charcoal);
}

.ticket-panel__tabpanel {
  display: flex;
  flex-direction: column;
  gap: 1.125rem;
}

/* The danger zone: a pale red card with a heavy bar on the left, kept a
   little further from the history above it than the blocks are from each
   other. The words are the body colour: 9.96:1 on the light ground, 13.03:1
   (#e6efed on #3a1d20) on the dark one, which the designer did not draw and
   which takes Overdue's dark red ground. */
.ticket-panel__delete {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.25rem;
  margin-top: 0.6rem;
  padding: 0.875rem 1rem 1rem 1.125rem;
  border: 1px solid var(--panel-danger);
  border-left-width: 4px;
  border-radius: 8px;
  background: var(--panel-danger-ground);
}

.ticket-panel__delete-title {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
}

.ticket-panel__delete-hint {
  margin: 0 0 0.5rem;
  font-size: 0.85rem;
  line-height: 1.5;
  color: var(--charcoal);
}

.ticket-panel__delete-button {
  min-height: 2rem;
  padding: 0.4rem 0.875rem;
  border: none;
  border-radius: 8px;
  background: #b3202c;
  color: #fff;
  font-family: inherit;
  font-weight: 600;
  font-size: 0.85rem;
  cursor: pointer;
}

.ticket-panel__delete-button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

@keyframes ticket-panel-in {
  from {
    transform: translateX(100%);
  }
  to {
    transform: translateX(0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .ticket-panel__sheet {
    animation: none;
  }
}
</style>
