<template>
  <!-- Status and assignee are two separate controls on purpose: the backend
       refuses a request carrying both, because each drives a different
       transition. Every control sends a patch with exactly one key.

       Each select sends on a choice, not on every change event: see
       onKeydown below for why the arrow keys only move what is shown. -->
  <div class="triage">
    <label class="triage__field">
      <span class="triage__label">Status</span>
      <select
        class="triage__select"
        aria-label="Change status"
        :value="shown('status')"
        :data-unsaved-choice="held.status === undefined ? undefined : 'true'"
        :aria-describedby="held.status === undefined ? undefined : statusId"
        @keydown="onKeydown('status', $event)"
        @keypress="onKeypress"
        @change="onChange('status', $event)"
        @blur="drop('status')"
      >
        <option v-for="(label, value) in TICKET_STATUS_LABELS" :key="value" :value="value">
          {{ label }}
        </option>
      </select>
    </label>

    <label class="triage__field">
      <span class="triage__label">Priority</span>
      <select
        class="triage__select"
        aria-label="Change priority"
        :value="shown('priority')"
        :data-unsaved-choice="held.priority === undefined ? undefined : 'true'"
        :aria-describedby="held.priority === undefined ? undefined : statusId"
        @keydown="onKeydown('priority', $event)"
        @keypress="onKeypress"
        @change="onChange('priority', $event)"
        @blur="drop('priority')"
      >
        <option v-for="(label, value) in TICKET_PRIORITY_LABELS" :key="value" :value="value">
          {{ label }}
        </option>
      </select>
    </label>

    <!-- Re-filing. With three categories a wrong one was tolerable; the
         client's eight include two near-synonyms ("General Question" and
         "Other") and two that overlap in practice (Registration and Account
         and access), so an agent will routinely know a ticket is filed wrong.
         Without this the category breakdown the client asked for on p52 fills
         with noise nobody can correct.

         Full option list, screening's own category included: a ticket message
         screening filed under Flagged content needs a way out, and a genuine
         child-safety report that came in through the form needs a way in. -->
    <label class="triage__field triage__field--wide">
      <span class="triage__label">Category</span>
      <select
        class="triage__select"
        aria-label="Change category"
        :value="shown('category')"
        :data-unsaved-choice="held.category === undefined ? undefined : 'true'"
        :aria-describedby="held.category === undefined ? undefined : statusId"
        @keydown="onKeydown('category', $event)"
        @keypress="onKeypress"
        @change="onChange('category', $event)"
        @blur="drop('category')"
      >
        <!-- A row written before tickets always carried a category, or one
             this list does not know, still shows what it is instead of a
             blank control. Disabled: it is not something to re-file INTO. -->
        <option v-if="!categoryKnown" :value="ticket.category" disabled>
          {{ categoryLabel(ticket.category) }}
        </option>
        <option v-for="option in TICKET_CATEGORY_OPTIONS" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>
    </label>

    <label class="triage__field triage__field--wide">
      <span class="triage__label">Assignee</span>
      <select
        class="triage__select"
        aria-label="Change assignee"
        :value="shown('assignee')"
        :data-unsaved-choice="held.assignee === undefined ? undefined : 'true'"
        :aria-describedby="held.assignee === undefined ? undefined : statusId"
        @keydown="onKeydown('assignee', $event)"
        @keypress="onKeypress"
        @change="onChange('assignee', $event)"
        @blur="drop('assignee')"
      >
        <!-- Handing a ticket back. Without this the owner control was
             one-way: a ticket picked up by mistake stayed in that person's
             name for good. -->
        <option :value="UNASSIGNED">Unassigned</option>
        <!-- The current owner, even when they are no longer on the assignable
             list. Without this row the control has no option matching its
             value and reads "Unassigned" (a blank, in a native select) for a
             ticket the queue still shows as theirs.

             The row says the person no longer works the queue rather than
             that they are inactive. Two different things drop somebody off
             the assignable list: their account being deactivated, and their
             queue access being revoked from the support agents page. The
             second leaves the account fully active, and People says so on the
             same screen, so "(inactive)" sent an admin to reactivate an
             account that was never switched off.

             The test has to be "are they missing from the rows we are about
             to render", not "are they missing from `assignees`". They are
             never missing from `assignees`: the endpoint returns one list for
             two consumers and deliberately keeps past owners in it, marking
             them assignable: false. Asking the wider question made this row
             unreachable and produced the exact fallback described above. -->
        <option v-if="ownerRow" :value="ownerRow.value">{{ ownerRow.label }}</option>
        <option v-for="person in assignable" :key="person.id" :value="String(person.id)">
          {{ person.name }}
        </option>
        <!-- Otherwise the rows above read as the whole platform, and
             "Unassigned" looks like the considered choice rather than the
             only one left. Worded for both states it covers: "could not be
             loaded" would itself be untrue while the request is still in
             flight. No "Try again" in this row: the loading case fixes
             itself, and the failed case has its own alert with a Try again
             button beside these controls (TicketDetailPanel). In React that
             sentence sat in the queue page's banner, because the queue page
             owned the request; the panel owns it now.

             `disabled` is load-bearing, not cosmetic. In the React panel the
             value "__unavailable" went through Number() to NaN, which
             JSON.stringify writes as null, the same body "Unassigned" sends:
             measured there, clicking this sentence un-assigned ticket #128.
             onChange below also refuses any value that is not the sentinel or
             a person's id, so neither guard depends on the other. -->
        <option v-if="assigneesUnavailable" :value="UNAVAILABLE" disabled>
          The assignee list has not loaded, so there is nobody else to pick here.
        </option>
      </select>
    </label>

    <!-- No optimistic update: a control shows the new value once the server
         has it, and snaps back (with the warning above the controls) when it
         refuses. The React selects gave no sign at all while a change was on
         its way (DT-15); this says so without taking the control away from
         the keyboard, which disabling it would.

         The same line tells a keyboard user that a value they moved to with
         the arrow keys is not saved yet, and how to save it. -->
    <p :id="statusId" class="triage__saving" role="status">{{ statusLine }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, useId } from 'vue'
import '@/components/support/ticketControls.css'

import type { TicketPatch } from '@/utils/ticketAgentAPI'
import {
  TICKET_CATEGORY_OPTIONS,
  TICKET_PRIORITY_LABELS,
  TICKET_STATUS_LABELS,
  UNASSIGNED,
  categoryLabel,
  type AssigneeOption,
  type TicketDetail
} from '@/utils/ticketAgentSchema'

const props = defineProps<{
  ticket: TicketDetail
  /** Everybody who could own a ticket, past owners included (assignable:
   *  false). Empty while the list is loading or after it failed. */
  assignees: AssigneeOption[]
  /** Whether the list is short because its request has not answered: still
   *  in flight, or failed. Without it the panel cannot tell "this person is
   *  off the queue" from "we have no roster to check them against", and says
   *  the first about whoever owns the ticket. */
  assigneesUnavailable: boolean
  /** Sends the patch. Resolves once the panel shows the server's answer,
   *  whether it took the change or refused it. */
  apply: (patch: TicketPatch) => Promise<void>
}>()

type Field = 'status' | 'priority' | 'category' | 'assignee'

const UNAVAILABLE = '__unavailable'

const assigneeValue = computed(() =>
  props.ticket.assignee ? String(props.ticket.assignee.id) : UNASSIGNED
)

const categoryKnown = computed(() =>
  TICKET_CATEGORY_OPTIONS.some((option) => option.value === props.ticket.category)
)

const assignable = computed(() => props.assignees.filter((person) => person.assignable))

const ownerRow = computed(() => {
  const owner = props.ticket.assignee
  if (!owner) return null
  if (props.assignees.some((person) => person.id === owner.id && person.assignable)) return null
  return {
    value: String(owner.id),
    // The claim needs a roster behind it. With no roster the owner is missing
    // from an empty list for a reason that has nothing to do with them, and
    // the plain name is what the queue row behind this panel already shows.
    label: props.assigneesUnavailable ? owner.name : `${owner.name} (no longer on the queue)`
  }
})

function currentValue(field: Field): string {
  if (field === 'assignee') return assigneeValue.value
  return props.ticket[field]
}

function patchFor(field: Field, picked: string): TicketPatch | null {
  if (field === 'status') return { status: picked }
  if (field === 'priority') return { priority: picked }
  if (field === 'category') return { category: picked }
  // The sentinel travels as a real JSON null, which is what the backend reads
  // as "back to the pool".
  if (picked === UNASSIGNED) return { assignee: null }
  // Anything else must be a person's id. The explanation row's value, or
  // anything else a script could set, is refused here rather than turned
  // into a number (NaN, then null, then an un-assigned ticket).
  return /^[1-9]\d*$/.test(picked) ? { assignee: Number(picked) } : null
}

const savingCount = ref(0)
const statusId = useId()

// --- Choosing versus looking --------------------------------------------------
//
// A native select fires `change` whenever its value moves, and on Windows and
// Linux (Chrome, Edge and Firefox) the arrow keys, Home, End, Page Up/Down and
// typed letters move the value of a closed, focused select straight away.
// That comes from how those browsers handle a closed select; it was not
// measured on Windows for this port, so check it there by hand once.
//
// If every `change` were sent, a keyboard agent looking down the Status list
// from In progress to Resolved would send two PATCHes: two system lines on the
// requester's timeline, and the resolved email to the student. On Assignee
// they would pick the ticket up in each person's name in turn. React's Radix
// Select only committed on Enter or a click: the arrow keys opened its list
// and moved a highlight (DT-08..DT-11).
//
// So a value reached by one of those keys is held: shown in the control, not
// sent, with a line saying so. Enter sends it; Esc or leaving the control puts
// the saved value back. A pick from the open list (a click, or Enter in the
// list) is a choice and is sent at once, as before.
//
// Measured for this port on macOS (headless Chromium 1228 and Playwright's
// WebKit, a static page with this same flag logic): a typed letter on a
// closed select moved the value and fired `change` at once, with the flag
// still up, so a Mac sends on a typed letter too without this. ArrowDown and
// End moved nothing there: on a Mac they open the list, which is why a hand
// test of the arrow keys on a Mac cannot show the problem this fixes.

/** What is showing in a control but not saved, per control. At most one at a
 *  time in practice: leaving a control drops its held value. */
const held = ref<Partial<Record<Field, string>>>({})

function shown(field: Field): string {
  return held.value[field] ?? currentValue(field)
}

const statusLine = computed(() => {
  const saving = savingCount.value > 0 ? 'Saving…' : ''
  const unsaved =
    Object.keys(held.value).length > 0 ? 'Not saved yet. Press Enter to save it, or Esc to undo.' : ''
  return [saving, unsaved].filter(Boolean).join(' ')
})

function drop(field: Field) {
  if (held.value[field] === undefined) return
  const next = { ...held.value }
  delete next[field]
  held.value = next
}

function hold(field: Field, value: string) {
  // Moving back to the saved value leaves nothing to save.
  if (value === currentValue(field)) {
    drop(field)
    return
  }
  held.value = { ...held.value, [field]: value }
}

// The keys a closed select acts on by itself, besides typed letters. A key
// held with Alt (Alt+ArrowDown opens the list) is marked too: whatever the
// key does, only a `change` it causes straight away is held.
const MOVE_KEYS = new Set([
  'ArrowUp',
  'ArrowDown',
  'ArrowLeft',
  'ArrowRight',
  'Home',
  'End',
  'PageUp',
  'PageDown'
])

// True from a moving key until the browser has finished acting on it. The
// select moves its value and fires `change` as the key's own default action,
// synchronously, after this handler returns and before any timer runs, so a
// zero timer clears it after exactly that one `change`. Not keyup: on a Mac
// the key that opens the list is followed by a keyup the list takes, and the
// flag would still be set when the agent picked from it.
let moving = false
let movingTimer: ReturnType<typeof setTimeout> | undefined

function onKeydown(field: Field, event: KeyboardEvent) {
  const select = event.target as HTMLSelectElement
  if (event.key === 'Enter') {
    const value = held.value[field]
    if (value === undefined) return
    event.preventDefault()
    void choose(field, value, select)
    return
  }
  if (event.key === 'Escape') {
    // The panel leaves this Esc alone while the control is marked
    // data-unsaved-choice, so it undoes the value instead of closing.
    if (held.value[field] === undefined) return
    event.preventDefault()
    drop(field)
    return
  }
  if (MOVE_KEYS.has(event.key) || typedLetter(event)) markMoving()
}

// Chrome and Firefox move the value for a typed letter on keypress, not
// keydown (their own select code; not measured here), and a browser may hand
// the keypress over in a later task than the keydown: by then the keydown's
// timer could already have cleared the flag. So the keypress marks it too.
function onKeypress(event: KeyboardEvent) {
  if (typedLetter(event)) markMoving()
}

function typedLetter(event: KeyboardEvent) {
  return event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey
}

function markMoving() {
  moving = true
  clearTimeout(movingTimer)
  movingTimer = setTimeout(() => {
    moving = false
  }, 0)
}

onBeforeUnmount(() => clearTimeout(movingTimer))

async function onChange(field: Field, event: Event) {
  const select = event.target as HTMLSelectElement
  if (moving) {
    hold(field, select.value)
    return
  }
  await choose(field, select.value, select)
}

/** Sends the choice. Resolves once the control shows the server's value. */
async function choose(field: Field, picked: string, select: HTMLSelectElement) {
  drop(field)
  const patch = patchFor(field, picked)
  if (patch) {
    savingCount.value += 1
    try {
      await props.apply(patch)
    } finally {
      savingCount.value -= 1
    }
  }
  // After a refusal the control must go back to the server's value. Vue
  // re-writes a bound select's value whenever this component re-renders, and
  // the Saving… counter above guarantees one, so today that already happens
  // (measured: deleting this line alone leaves the snap-back test green).
  // This line keeps it from depending on that counter.
  await nextTick()
  select.value = shown(field)
}
</script>

<style scoped>
/* One row across the panel, in the first redesign round's (October 2026)
   proportions: Status 132, Priority 104, Category 220, Assignee 132, which is
   the 624px a full-width panel has once the gaps are out. A narrower panel
   shrinks them in the same proportions and wraps when that gets too tight.

   Measured on the panel's ground (WCAG AA: 4.5:1 for text, 3:1 for a
   control's edge):
     light  labels #5a6268 on #ffffff 6.21:1   edge #84938f 3.21:1
     dark   labels #a3b3ae on #1d2826 6.95:1   edge #70827d on the #161f1d field 4.15:1 */
.triage {
  --triage-muted: #5a6268;
  --triage-edge: #84938f;

  position: relative;
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 0.6rem 0.75rem;
}

:root[data-theme='dark'] .triage {
  --triage-muted: #a3b3ae;
  --triage-edge: #70827d;
}

.triage__field {
  display: flex;
  flex: 132 1 0;
  flex-direction: column;
  gap: 0.2rem;
  min-width: 6.5rem;
}

.triage__field:nth-child(2) {
  flex-grow: 104;
}

.triage__field--wide:nth-child(3) {
  flex-grow: 220;
}

.triage__label {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--triage-muted);
}

/* The thin chevron from ticketControls.css in place of the browser's. */
.triage__select {
  width: 100%;
  height: 2.5rem;
  padding: 0.25rem 2.25rem 0.25rem 0.875rem;
  border: 1px solid var(--triage-edge);
  border-radius: 8px;
  background: var(--white);
  background-image: var(--ticket-select-chevron);
  background-repeat: no-repeat;
  background-position: right 0.9rem center;
  appearance: none;
  color: var(--charcoal);
  font-family: inherit;
  font-size: 0.85rem;
  text-overflow: ellipsis;
}

/* Hung just under the row rather than given a row of its own: the design
   leaves no blank line for it, and the panel's gap above the tabs has room
   for one line of it. It is in the page, empty, before anything is said, as
   a status region has to be to be read out. */
.triage__saving {
  position: absolute;
  top: calc(100% + 0.15rem);
  left: 0;
  margin: 0;
  font-size: 0.8rem;
  color: var(--triage-muted);
}
</style>
