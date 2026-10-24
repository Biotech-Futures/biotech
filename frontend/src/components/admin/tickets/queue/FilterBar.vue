<template>
  <div class="queue-filters">
    <input
      v-model="searchDraft"
      type="search"
      class="queue-filters__search"
      placeholder="Search number, subject, or requester"
      aria-label="Search tickets"
    />

    <!-- Five lists with check boxes, so that several of a kind can be picked
         (client item C-27, 2026-10-22). Nothing ticked is "Any ...", no
         filter; the request leaves an empty list out (ticketAgentAPI
         activeFilters). -->
    <QueueFilterSelect
      class="queue-filters__select queue-filters__select--status"
      aria-label="Filter by status"
      any-label="Any status"
      :model-value="filters.status ?? []"
      :options="statusOptions"
      @change="set('status', $event)"
    />

    <QueueFilterSelect
      class="queue-filters__select queue-filters__select--priority"
      aria-label="Filter by priority"
      any-label="Any priority"
      :model-value="filters.priority ?? []"
      :options="priorityOptions"
      @change="set('priority', $event)"
    />

    <QueueFilterSelect
      class="queue-filters__select queue-filters__select--category"
      aria-label="Filter by category"
      any-label="Any category"
      :model-value="filters.category ?? []"
      :options="TICKET_CATEGORY_OPTIONS"
      @change="set('category', $event)"
    />

    <!-- The server lists the regions in use, A to Z, then the Unknown bucket
         as its own value (UNKNOWN_REGION): an empty parameter would read as
         "no filter". -->
    <QueueFilterSelect
      class="queue-filters__select queue-filters__select--region"
      aria-label="Filter by region"
      any-label="Any region"
      :model-value="filters.region ?? []"
      :options="regions"
      @change="set('region', $event)"
    />

    <!-- Unassigned is the bucket the Unassigned card counts; it is not one of
         the people, so it is listed by hand rather than coming from the
         assignee options endpoint. Deactivated agents stay in the list on
         purpose: their tickets did not move when the account was switched
         off, and this is the only way to find that work in bulk. -->
    <QueueFilterSelect
      class="queue-filters__select queue-filters__select--assignee"
      aria-label="Filter by assignee"
      any-label="Any assignee"
      :model-value="filters.assignee ?? []"
      :options="assigneeOptions"
      @change="set('assignee', $event)"
    />

    <!-- Back to the view the queue opens on (C-28: every status but
         Resolved), not to nothing at all: that view is the queue at rest, so
         it shows whenever anything else is chosen. -->
    <button
      v-if="hasAny"
      type="button"
      class="queue-filters__clear"
      @click="emit('change', restingFilters())"
    >
      Clear filters
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import {
  OVERDUE,
  TICKET_CATEGORY_OPTIONS,
  TICKET_PRIORITY_LABELS,
  TICKET_STATUS_LABELS,
  UNASSIGNED,
  type AssigneeOption,
  type RegionOption,
  type TicketFilters
} from '@/utils/ticketAgentSchema'

import QueueFilterSelect from './QueueFilterSelect.vue'
import { isRestingView, restingFilters, type FilterOption } from './queueFilters'

const props = defineProps<{
  filters: TicketFilters
  regions: RegionOption[]
  assignees: AssigneeOption[]
}>()

const emit = defineEmits<{ change: [next: TicketFilters] }>()

type ListKey = 'region' | 'status' | 'category' | 'assignee' | 'priority'

function set(key: ListKey, values: string[]) {
  emit('change', { ...props.filters, [key]: values })
}

// The statuses, then Overdue: not a status a ticket is saved with but the one
// the Overdue badge beside the status marks, and where the Overdue card lands.
// Ticked beside statuses it is one more way in (services/queue.py).
const statusOptions: FilterOption[] = [
  ...Object.entries(TICKET_STATUS_LABELS).map(([value, label]) => ({ value, label })),
  { value: OVERDUE, label: 'Overdue', extra: true }
]

const priorityOptions: FilterOption[] = Object.entries(TICKET_PRIORITY_LABELS).map(([value, label]) => ({ value, label }))

const assigneeOptions = computed<FilterOption[]>(() => [
  { value: UNASSIGNED, label: 'Unassigned' },
  ...props.assignees.map((person) => ({ value: String(person.id), label: person.name }))
])

// The box types locally and only settles upward, so "SUP-2026" is one queue
// request instead of eight. Every keystroke used to raise the filters, and
// each of those is a COUNT plus a page of rows against the whole table. 300ms
// is what React used, and it sits between the portal's own search boxes
// (AdminGroupsPage 300ms, useAdminUsersView 350ms).
const SEARCH_SETTLE_MS = 300

const searchDraft = ref(props.filters.search ?? '')
let settleTimer: ReturnType<typeof setTimeout> | undefined

watch(searchDraft, (value) => {
  clearTimeout(settleTimer)
  settleTimer = setTimeout(() => {
    // Only when the settled value differs from what is already applied, and
    // read at settling time: comparing against the filters as they were
    // when typing began would undo another filter picked in between.
    if (value !== (props.filters.search ?? '')) {
      emit('change', { ...props.filters, search: value })
    }
  }, SEARCH_SETTLE_MS)
})

// Keeps the box in step when the parent resets the filters: the Clear button
// sets them to {} and nothing else would empty the input.
watch(
  () => props.filters.search,
  (value) => {
    searchDraft.value = value ?? ''
  }
)

onBeforeUnmount(() => clearTimeout(settleTimer))

const hasAny = computed(() => !isRestingView(props.filters))
</script>

<style scoped>
/* The first redesign round (October 2026) puts all six on one row at a
   1440px screen: the search takes a share and a half, each list one share,
   and Clear filters sits at the far end when there is something to clear.
   The search keeps a floor wide enough for its whole placeholder, which the
   designer's narrower box cut off at "or reque".

   Edges, measured against the 3:1 a control's boundary needs:
     light  #84938f on the white field 3.21:1, on the #f8f9fa page 3.04:1
     dark   #70827d on the #161f1d field 4.15:1, on the #0f1715 page 4.49:1
   The designer kept the dark queue's colours, but its edge, --border-light,
   is 1.39:1 there; #70827d is the edge his other dark screens use.

   Clear filters under the pointer takes the queue's pale green, #e8f5ee
   (#017151 on it 5.38:1), not --accent-green-soft, the peach in the light
   theme (C-20). Dark keeps the theme's translucent green. */
.queue-filters {
  --queue-filter-edge: #84938f;
  --queue-filter-placeholder: #6c757d;
  --queue-filter-wash: #e8f5ee;

  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.625rem;
}

:root[data-theme='dark'] .queue-filters {
  --queue-filter-edge: #70827d;
  --queue-filter-placeholder: var(--text-muted);
  --queue-filter-wash: var(--accent-green-soft);
}

.queue-filters__search,
.queue-filters__select {
  height: 2.5rem;
  padding: 0.25rem 0.75rem;
  border: 1px solid var(--queue-filter-edge);
  border-radius: 8px;
  background: var(--white);
  color: var(--teal);
  font: inherit;
  font-size: 0.9rem;
}

/* Each list starts from its padding (50px with the room for the chevron), so
   the search starts from half as much again: then it really is a share and a
   half, as the designer drew it. */
.queue-filters__search {
  flex: 1.5 1 4.6875rem;
  min-width: 16.5rem;
  max-width: 100%;
}

/* Clear filters takes its share of the row once something is filtered, and
   with the search held at its floor the lists gave it up: "Any assignee" was
   cut to "Any assign…". The designer's A-12 narrows the search instead
   (219px against 237px), which is also when its placeholder matters least. */
.queue-filters:has(.queue-filters__clear) .queue-filters__search {
  min-width: 12rem;
}

.queue-filters__search::placeholder {
  color: var(--queue-filter-placeholder);
  opacity: 1;
}

/* The lists' boxes (QueueFilterSelect), with room kept clear on the right
   for the chevron it draws as AppSelect does. */
.queue-filters__select {
  flex: 1 1 0;
  min-width: 0;
  padding-right: 2.25rem;
}

/* A text button, green on the page ground (5.72:1 on --bg-light). The theme
   does not redefine --dark-green, which is 3.02:1 on the dark ground, so dark
   takes the mint that the theme leaves alone (6.63:1 there). The negative
   margin puts the words, not the hover pill, flush with the table's edge. */
.queue-filters__clear {
  margin-left: auto;
  margin-right: -0.6rem;
  padding: 0.35rem 0.6rem;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--dark-green);
  font: inherit;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
}

.queue-filters__clear:hover {
  background: var(--queue-filter-wash);
  color: var(--dark-green);
}

:root[data-theme='dark'] .queue-filters__clear,
:root[data-theme='dark'] .queue-filters__clear:hover {
  color: var(--mint-green);
}

@media (max-width: 640px) {
  .queue-filters__search,
  .queue-filters__select {
    flex: 1 1 100%;
    width: 100%;
  }
}
</style>
