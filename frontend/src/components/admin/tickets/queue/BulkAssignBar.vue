<template>
  <!-- "Clear selection" rather than the bar's default "Clear": React's
       button read "Clear" and was named "Clear selection" for a screen
       reader, and this bar has one label for both. It also sits a few inches
       from "Clear filters", which is a different thing to clear. -->
  <BulkActionsBar
    :count="count"
    noun="ticket"
    clear-label="Clear selection"
    :disabled="pending"
    @clear="emit('clear')"
  >
    <select v-model="choice" class="bulk-assign__select" aria-label="Assign to">
      <option value="" disabled>Assign to…</option>
      <!-- The pool, under the name the filter bar already calls it by. The
           batch endpoint has always taken a null assignee, the way the
           single-ticket PATCH does, but nothing here could say it: an agent
           who swept twenty tickets onto themselves by mistake had twenty
           separate visits to the detail panel to undo it. Above the names
           rather than below, again matching the filter bar. -->
      <option :value="UNASSIGNED">Unassigned</option>
      <!-- Same filter as the detail panel's assign control. The endpoint
           returns one list for two consumers: the filter dropdown wants every
           past owner, this one wants only people the write path will accept.
           Without the filter a deactivated or revoked agent was offered here
           and the whole batch came back 400. -->
      <option v-for="person in assignable" :key="person.id" :value="String(person.id)">
        {{ person.name }}
      </option>
      <!-- Said here as well as in the page's banner, because this list is not
           empty any more: the pool line above it is always offered, so a
           failed endpoint leaves a dropdown that opens on one plausible
           option and reads as the whole platform. A disabled option rather
           than loose text, which is the shape the group dialogs already use
           for a list with nothing to offer. -->
      <option v-if="assigneesUnavailable" value="__unavailable" disabled>
        The assignee list could not be loaded, so there is nobody to pick here. Reload to try
        again.
      </option>
      <!-- The same trap while the list is still on its way: the pool line on
           its own reads as a platform with nobody on it. React told the panel
           about a pending roster (P9-1) but not this dropdown (U2 GAP-15). -->
      <option v-else-if="assigneesLoading" value="__loading" disabled>
        Loading the assignee list…
      </option>
    </select>

    <button
      type="button"
      class="btn btn-primary btn-sm bulk-assign__go"
      :disabled="!choice || pending || overBatchLimit"
      :aria-describedby="overBatchLimit ? limitNoteId : undefined"
      @click="assign"
    >
      {{ pending ? workingLabel : label }}
    </button>

    <!-- The server refuses a batch of more than 200 ids with a 400
         (serializers_admin.py BulkAssignSerializer). The selection survives
         paging and pages hold up to 100 rows, so three full pages are enough
         to reach it, and React then showed the rejected-request sentence,
         whose advice ("check the person you picked", "try again") is not
         true of this and fails the same way every time (U2 GAP-05). -->
    <p v-if="overBatchLimit" :id="limitNoteId" class="bulk-assign__limit">
      One batch can hold at most {{ BATCH_LIMIT }} tickets, and {{ count }} are selected.
      Deselect some to assign the rest.
    </p>
  </BulkActionsBar>
</template>

<script setup lang="ts">
import { computed, ref, useId } from 'vue'

import BulkActionsBar from '@/components/admin/BulkActionsBar.vue'
import { UNASSIGNED, type AssigneeOption } from '@/utils/ticketAgentSchema'
import { BULK_ASSIGN_LIMIT as BATCH_LIMIT } from './queueRules'

const props = defineProps<{
  count: number
  assignees: AssigneeOption[]
  /** Whether the list is empty because its endpoint failed. Without it a
   *  dead endpoint and a platform with nobody on it look identical in here,
   *  and the pool line makes the short list look complete. */
  assigneesUnavailable: boolean
  /** Whether the list has not answered yet. */
  assigneesLoading: boolean
  pending: boolean
}>()

const emit = defineEmits<{
  clear: []
  assign: [assigneeId: number | null]
}>()

const limitNoteId = useId()

// Local to the bar, as in React: it resets when the bar goes (the selection
// emptied), and it stays after a refused request so the agent can press
// again.
const choice = ref('')

const assignable = computed(() => props.assignees.filter((person) => person.assignable))

const toThePool = computed(() => choice.value === UNASSIGNED)
// "Assign" is the wrong word for handing a batch back, and the button is the
// last thing an agent reads before pressing it.
const label = computed(() => (toThePool.value ? 'Unassign' : 'Assign'))
const workingLabel = computed(() => (toThePool.value ? 'Unassigning…' : 'Assigning…'))

const overBatchLimit = computed(() => props.count > BATCH_LIMIT)

function assign() {
  if (!choice.value) return
  // null is what sends a ticket back to the pool; JSON.stringify keeps a
  // null, so it arrives as null rather than being dropped. A person goes as a
  // number, not the string "2": the id lands in a JSON body the serializer
  // validates as a primary key.
  emit('assign', toThePool.value ? null : Number(choice.value))
}
</script>

<style scoped>
.bulk-assign__select {
  width: 200px;
  max-width: 100%;
  height: 2.1rem;
  padding: 0.25rem 0.5rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--white);
  color: var(--charcoal);
  font: inherit;
  font-size: 0.875rem;
}

/* Literal #fff: .btn-primary's var(--white) is a surface colour that turns
   near-black in the dark theme, 2.79:1 on this green. #fff is 6.03:1. */
.bulk-assign__go,
.bulk-assign__go:hover,
.bulk-assign__go:disabled:hover {
  color: #fff;
}

/* On the bar's --light-green wash: #a71d2a is 6.43:1 there in light mode;
   dark takes the theme's --danger, 5.72:1 on that wash over the dark page. */
.bulk-assign__limit {
  flex-basis: 100%;
  margin: 0;
  color: #a71d2a;
  font-size: 0.85rem;
  font-weight: 600;
}

:root[data-theme='dark'] .bulk-assign__limit {
  color: var(--danger);
}

/* The shared bar's Clear button is var(--dark-green) on the bar's
   --light-green wash. The dark theme redefines the wash, rgba(1,113,81,.18),
   and leaves --dark-green alone, so in dark it is green on green: 2.62:1 over
   the dark page, 2.42:1 hovered. Mint, which the theme also leaves alone, is
   5.75:1 and 5.31:1 there. Light keeps the bar's own green (5.27:1, 4.58:1
   hovered).
   Fixed here rather than in BulkActionsBar.vue, which is Team 1's and has the
   same failure on every admin page that uses it.
   The bar is this component's root element, so it carries this component's
   scope id, and `.bulk-actions-bar` is where that id has to go: written as
   `:root[data-theme='dark'] :deep(...)` the id lands on :root itself, which
   never carries it, and the rule matches nothing
   (bulkAssignBarContrast.spec.ts checks the compiled selector against the
   mounted button). */
:root[data-theme='dark'] .bulk-actions-bar :deep(.bulk-actions-bar__clear) {
  color: var(--mint-green);
}
</style>
