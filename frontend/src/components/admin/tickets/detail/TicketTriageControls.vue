<template>
  <!-- Status and assignee are two separate controls on purpose: the backend
       refuses a request carrying both, because each drives a different
       transition. Every control sends a patch with exactly one key.

       The platform's own dropdown (AppSelect) since the 2026-10-22 client
       meeting (C-29). It changes nothing until a choice is picked, with a
       click or with Enter in its open list: the arrow keys open the list and
       move through it. The native selects these replace moved their value on
       the arrow keys of a closed control on Windows and Linux, and this
       component used to hold such a value back until Enter; AppSelect has no
       such move, so every change it reports is a choice, sent at once. -->
  <div class="triage">
    <div class="triage__field">
      <span class="triage__label">Status</span>
      <AppSelect
        class="triage__select"
        aria-label="Change status"
        :model-value="currentValue('status')"
        :options="STATUS_OPTIONS"
        :searchable="false"
        @change="(value) => choose('status', String(value))"
      />
    </div>

    <div class="triage__field">
      <span class="triage__label">Priority</span>
      <AppSelect
        class="triage__select"
        aria-label="Change priority"
        :model-value="currentValue('priority')"
        :options="PRIORITY_OPTIONS"
        :searchable="false"
        @change="(value) => choose('priority', String(value))"
      />
    </div>

    <!-- Re-filing. With three categories a wrong one was tolerable; the
         client's eight include two near-synonyms ("General Question" and
         "Other") and two that overlap in practice (Registration and Account
         and access), so an agent will routinely know a ticket is filed wrong.
         Without this the category breakdown the client asked for on p52 fills
         with noise nobody can correct.

         Full option list, screening's own category included: a ticket message
         screening filed under Flagged content needs a way out, and a genuine
         child-safety report that came in through the form needs a way in. -->
    <div class="triage__field triage__field--wide">
      <span class="triage__label">Category</span>
      <AppSelect
        class="triage__select"
        aria-label="Change category"
        :model-value="currentValue('category')"
        :options="categoryOptions"
        :searchable="false"
        @change="(value) => choose('category', String(value))"
      />
    </div>

    <div class="triage__field triage__field--wide">
      <span class="triage__label">Assignee</span>
      <AppSelect
        class="triage__select"
        aria-label="Change assignee"
        :model-value="currentValue('assignee')"
        :options="assigneeOptions"
        :searchable="false"
        @change="(value) => choose('assignee', String(value))"
      />
    </div>

    <!-- No optimistic update: a control shows the new value once the server
         has it, and snaps back (with the warning above the controls) when it
         refuses, because each one shows the ticket the server sent. The React
         selects gave no sign at all while a change was on its way (DT-15);
         this says so without taking the control away from the keyboard,
         which disabling it would. -->
    <p class="triage__saving" role="status">{{ savingCount > 0 ? 'Saving…' : '' }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

import AppSelect, { type AppSelectOption } from '@/components/AppSelect.vue'
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


const STATUS_OPTIONS: AppSelectOption[] = Object.entries(TICKET_STATUS_LABELS).map(([value, label]) => ({
  value,
  label
}))
const PRIORITY_OPTIONS: AppSelectOption[] = Object.entries(TICKET_PRIORITY_LABELS).map(([value, label]) => ({
  value,
  label
}))

const assigneeValue = computed(() =>
  props.ticket.assignee ? String(props.ticket.assignee.id) : UNASSIGNED
)

const categoryKnown = computed(() =>
  TICKET_CATEGORY_OPTIONS.some((option) => option.value === props.ticket.category)
)

const categoryOptions = computed<AppSelectOption[]>(() => [
  // A row written before tickets always carried a category, or one this list
  // does not know, still shows what it is instead of a blank control.
  // Disabled: it is not something to re-file INTO.
  ...(categoryKnown.value
    ? []
    : [{ value: props.ticket.category, label: categoryLabel(props.ticket.category), disabled: true }]),
  ...TICKET_CATEGORY_OPTIONS.map(({ value, label }) => ({ value, label }))
])

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

const assigneeOptions = computed<AppSelectOption[]>(() => [
  // Handing a ticket back. Without this the owner control was one-way: a
  // ticket picked up by mistake stayed in that person's name for good.
  { value: UNASSIGNED, label: 'Unassigned' },
  // The current owner, even when they are no longer on the assignable list.
  // Without this row the control has nothing matching its value and reads
  // blank for a ticket the queue still shows as theirs.
  //
  // The row says the person no longer works the queue rather than that they
  // are inactive. Two different things drop somebody off the assignable
  // list: their account being deactivated, and their queue access being
  // revoked. The second leaves the account fully active, and People says so
  // on the same screen, so "(inactive)" sent an admin to reactivate an
  // account that was never switched off.
  //
  // The test has to be "are they missing from the rows we are about to
  // render", not "are they missing from `assignees`". They are never missing
  // from `assignees`: the endpoint returns one list for two consumers and
  // deliberately keeps past owners in it, marking them assignable: false.
  // Asking the wider question made this row unreachable.
  ...(ownerRow.value ? [ownerRow.value] : []),
  ...assignable.value.map((person) => ({ value: String(person.id), label: person.name })),
  // Otherwise the rows above read as the whole platform, and "Unassigned"
  // looks like the considered choice rather than the only one left. Worded
  // for both states it covers: "could not be loaded" would itself be untrue
  // while the request is still in flight. The failed case has its own alert
  // with a Try again button beside these controls (TicketDetailPanel).
  //
  // `disabled` is load-bearing, not cosmetic. In the React panel this row's
  // value went through Number() to NaN, which JSON.stringify writes as null,
  // the same body "Unassigned" sends: measured there, clicking this sentence
  // un-assigned ticket #128. patchFor below also refuses any value that is
  // not the sentinel or a person's id, so neither guard depends on the other.
  // Split over two lines because AppSelect keeps each line to one row.
  ...(props.assigneesUnavailable
    ? [
        {
          value: UNAVAILABLE,
          label: 'Nobody else to pick here',
          detail: 'The assignee list has not loaded.',
          disabled: true
        }
      ]
    : [])
])

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

/** Sends the choice. Each control shows the ticket the server sent, so after
 *  a refusal it is already back on the server's value. */
async function choose(field: Field, picked: string) {
  const patch = patchFor(field, picked)
  if (!patch) return
  savingCount.value += 1
  try {
    await props.apply(patch)
  } finally {
    savingCount.value -= 1
  }
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

/* The box: the panel's field edge and height. AppSelect draws the chevron
   and the list. */
.triage__select {
  display: block;
  width: 100%;
  height: 2.5rem;
  padding: 0.25rem 0.875rem;
  border: 1px solid var(--triage-edge);
  border-radius: 8px;
  background: var(--white);
  color: var(--teal);
  font-family: inherit;
  font-size: 0.85rem;
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

/* AppSelect rings its box in --dark-green when its field has keyboard focus,
   which the dark theme does not redefine: about 2.8:1 on the dark grounds,
   under the 3:1 a focus indicator needs. The panel's own dark accent, as its other controls take. */
:root[data-theme='dark'] .triage__select:has(:focus-visible) {
  outline-color: #5ea99e;
}
</style>
