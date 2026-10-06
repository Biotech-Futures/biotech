<template>
  <div class="queue-filters">
    <input
      v-model="searchDraft"
      type="search"
      class="queue-filters__search"
      placeholder="Search number, subject, or requester"
      aria-label="Search tickets"
    />

    <!-- "Any ..." is an empty value. React needed an "__any__" sentinel here
         because its Select component cannot carry an empty value; a native
         select can, so "no filter" is simply "" and is dropped when the
         request is built (ticketAgentAPI appendFilters). -->
    <select
      class="queue-filters__select queue-filters__select--status"
      aria-label="Filter by status"
      :value="filters.status || ''"
      @change="set('status', $event)"
    >
      <option value="">Any status</option>
      <option v-for="(label, value) in TICKET_STATUS_LABELS" :key="value" :value="value">
        {{ label }}
      </option>
    </select>

    <select
      class="queue-filters__select queue-filters__select--priority"
      aria-label="Filter by priority"
      :value="filters.priority || ''"
      @change="set('priority', $event)"
    >
      <option value="">Any priority</option>
      <option v-for="(label, value) in TICKET_PRIORITY_LABELS" :key="value" :value="value">
        {{ label }}
      </option>
    </select>

    <select
      class="queue-filters__select queue-filters__select--category"
      aria-label="Filter by category"
      :value="filters.category || ''"
      @change="set('category', $event)"
    >
      <option value="">Any category</option>
      <option v-for="option in TICKET_CATEGORY_OPTIONS" :key="option.value" :value="option.value">
        {{ option.label }}
      </option>
    </select>

    <select
      class="queue-filters__select queue-filters__select--region"
      aria-label="Filter by region"
      :value="filters.region || ''"
      @change="set('region', $event)"
    >
      <option value="">Any region</option>
      <!-- The server lists the regions in use, A to Z, then the Unknown
           bucket as its own value (UNKNOWN_REGION): an empty parameter would
           read as "no filter". -->
      <option v-for="region in regions" :key="region.value" :value="region.value">
        {{ region.label }}
      </option>
    </select>

    <select
      class="queue-filters__select queue-filters__select--assignee"
      aria-label="Filter by assignee"
      :value="filters.assignee || ''"
      @change="set('assignee', $event)"
    >
      <option value="">Any assignee</option>
      <!-- The bucket the Unassigned card counts. Not one of the people below,
           so it is listed by hand rather than coming from the assignee options
           endpoint. -->
      <option :value="UNASSIGNED">Unassigned</option>
      <!-- Deactivated agents stay here on purpose: their tickets did not move
           when the account was switched off, and this is the only way to find
           that work in bulk. -->
      <option v-for="person in assignees" :key="person.id" :value="String(person.id)">
        {{ person.name }}
      </option>
    </select>

    <button
      v-if="hasAny"
      type="button"
      class="queue-filters__clear"
      @click="emit('change', {})"
    >
      Clear filters
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import {
  TICKET_CATEGORY_OPTIONS,
  TICKET_PRIORITY_LABELS,
  TICKET_STATUS_LABELS,
  UNASSIGNED,
  type AssigneeOption,
  type RegionOption,
  type TicketFilters
} from '@/utils/ticketAgentSchema'

const props = defineProps<{
  filters: TicketFilters
  regions: RegionOption[]
  assignees: AssigneeOption[]
}>()

const emit = defineEmits<{ change: [next: TicketFilters] }>()

// "" for "Any", stored as an empty string rather than a deleted key, the way
// React stored it. The request drops every falsy value either way.
function set(key: keyof TicketFilters, event: Event) {
  const value = (event.target as HTMLSelectElement).value
  emit('change', { ...props.filters, [key]: value })
}

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

const hasAny = computed(() => Object.values(props.filters).some(Boolean))
</script>

<style scoped>
.queue-filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}

.queue-filters__search,
.queue-filters__select {
  height: 2.25rem;
  padding: 0.25rem 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--white);
  color: var(--charcoal);
  font: inherit;
  font-size: 0.9rem;
}

.queue-filters__search {
  width: 18rem;
  max-width: 100%;
}

.queue-filters__select--status {
  width: 150px;
}

.queue-filters__select--priority {
  width: 140px;
}

.queue-filters__select--category {
  width: 190px;
}

.queue-filters__select--region {
  width: 160px;
}

.queue-filters__select--assignee {
  width: 170px;
}

/* A text button, green on the page ground (5.72:1 on --bg-light). The theme
   does not redefine --dark-green, which is 3.02:1 on the dark ground, so dark
   takes the mint that the theme leaves alone (6.63:1 there). */
.queue-filters__clear {
  padding: 0.35rem 0.6rem;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--dark-green);
  font: inherit;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
}

.queue-filters__clear:hover {
  background: var(--accent-green-soft);
  color: var(--dark-green);
}

:root[data-theme='dark'] .queue-filters__clear,
:root[data-theme='dark'] .queue-filters__clear:hover {
  color: var(--mint-green);
}

@media (max-width: 640px) {
  .queue-filters__search,
  .queue-filters__select {
    width: 100%;
  }
}
</style>
