<template>
  <div class="ticket-analytics">
    <header>
      <!-- An h2, not the h1 React had: the section shell above
           (TicketsSection.vue) holds the page's only h1 and names the
           section, this names the tab inside it. The card titles below are
           h3 and the chart titles h4, one level under each. -->
      <h2 class="ticket-analytics__title">Ticket analytics</h2>
      <p class="ticket-analytics__subtitle">
        Dates are read as UTC, the same rule the ticket numbering uses. A window that starts on
        1 March opens at 11am Sydney time.
      </p>
    </header>

    <!-- Filters in one row above the charts. Held on the page, not on the
         URL, as in React. -->
    <div class="ticket-analytics__filters">
      <div class="ticket-analytics__field">
        <label for="ticket-analytics-from" class="ticket-analytics__label">From</label>
        <!-- Sent exactly as the input gives it, YYYY-MM-DD. The server alone
             makes a bare `to` inclusive by adding a day; doing it here as well
             would count that day twice (views_admin.py _window_bound). A
             native input on purpose: a picker whose value is a local-midnight
             timestamp sends the day before for every reader east of UTC once
             it goes through toISOString. -->
        <input
          id="ticket-analytics-from"
          v-model="from"
          type="date"
          class="ticket-analytics__input"
        />
      </div>
      <div class="ticket-analytics__field">
        <label for="ticket-analytics-to" class="ticket-analytics__label">To</label>
        <input id="ticket-analytics-to" v-model="to" type="date" class="ticket-analytics__input" />
      </div>
      <!-- The native date input renders in the browser's locale, which shows
           "mm/dd/yyyy" on a machine set to US English while the platform's
           users are in Australia, and 03/09 is two different days depending
           on which you assume. The control cannot be told otherwise, so the
           window it produced is echoed back below in a form with no ambiguity
           in it: a named month, and the word "inclusive", since the closing
           date counts the whole day. -->
      <div class="ticket-analytics__field">
        <label for="ticket-analytics-dimension" class="ticket-analytics__label">Break down by</label>
        <select
          id="ticket-analytics-dimension"
          v-model="dimension"
          class="ticket-analytics__input ticket-analytics__select"
        >
          <!-- The list comes from the payload, so a failed request leaves
               nothing to offer. Falling back to the chosen dimension rather
               than to "region" keeps the control naming what is selected
               instead of going blank. -->
          <option v-for="option in dimensionOptions" :key="option" :value="option">
            {{ dimensionLabel(option) }}
          </option>
        </select>
      </div>
    </div>

    <p v-if="from || to" class="ticket-analytics__window">{{ describeWindow(from, to) }}</p>

    <!-- Unlike the audit page, a failure leaves the controls in place, so a
         window the server refused can be fixed where it was typed. -->
    <p v-if="errorMessage" class="ticket-analytics__error" role="alert">{{ errorMessage }}</p>
    <p v-if="loading" class="ticket-analytics__loading">Loading…</p>

    <div v-if="data" class="ticket-analytics__grid">
      <section class="ticket-analytics__card" aria-labelledby="ticket-analytics-demand">
        <h3 id="ticket-analytics-demand" class="ticket-analytics__card-title">
          Demand · what help is being requested?
        </h3>
        <StatTile
          label="Tickets raised"
          :value="String(data.demand.volume)"
          hint="In the selected window"
        />
        <div>
          <h4 class="ticket-analytics__chart-title">By category</h4>
          <MeasureBars label="By category" :rows="categoryRows" />
        </div>
        <div>
          <h4 class="ticket-analytics__chart-title">By channel</h4>
          <MeasureBars label="By channel" :rows="channelRows" />
        </div>
      </section>

      <section class="ticket-analytics__card" aria-labelledby="ticket-analytics-flow">
        <h3 id="ticket-analytics-flow" class="ticket-analytics__card-title">
          Flow · where does work slow down?
        </h3>
        <div class="ticket-analytics__tiles">
          <StatTile
            label="Unassigned"
            :value="String(data.flow.unassignedBacklog)"
            hint="Nobody has picked it up"
          />
          <StatTile label="Reopens" :value="String(data.flow.reopens)" hint="Counted per event" />
          <StatTile
            label="Hand-offs"
            :value="String(data.flow.handOffs)"
            hint="Passed to someone else"
          />
        </div>
        <div>
          <h4 class="ticket-analytics__chart-title">Time since anything happened</h4>
          <MeasureBars
            label="Time since anything happened"
            :rows="ageRows"
            :format="duration"
            empty-message="Nothing open in this window."
          />
        </div>
      </section>

      <section class="ticket-analytics__card" aria-labelledby="ticket-analytics-service">
        <h3 id="ticket-analytics-service" class="ticket-analytics__card-title">
          Service · how quickly do we respond?
        </h3>
        <div class="ticket-analytics__tiles">
          <StatTile
            label="First reply"
            :value="duration(data.service.firstResponseSeconds)"
            :hint="`Average of ${data.service.answeredCount} answered`"
          />
          <StatTile
            label="To resolve"
            :value="duration(data.service.resolutionSeconds)"
            :hint="`Average of ${data.service.resolvedCount} resolved`"
          />
          <!-- Not "no first reply" any more. The client replaced that rule on
               2026-09-04: the clock restarts every time the requester writes
               and stops every time support answers, so a ticket already
               answered once can still be late. The tile beside this one is
               where first replies are measured.

               Word for word what the queue's Overdue card says. The same
               number on two screens has to read as the same number. -->
          <StatTile
            label="Overdue"
            :value="String(data.service.overdue)"
            hint="Waiting on support for longer than its priority allows"
          />
        </div>
      </section>

      <section class="ticket-analytics__card" aria-labelledby="ticket-analytics-quality">
        <h3 id="ticket-analytics-quality" class="ticket-analytics__card-title">
          Quality · did the support help?
        </h3>
        <div class="ticket-analytics__tiles">
          <StatTile
            label="Resolved"
            :value="resolvedShare"
            :hint="`${data.quality.resolvedCount} of ${data.quality.totalCount}`"
          />
          <StatTile
            label="Came back"
            :value="String(data.quality.repeatContacts)"
            hint="People with more than one"
          />
          <!-- Says why rather than showing a zero. A satisfaction score of
               nought is a damning number to invent for a survey that was
               never sent. -->
          <StatTile
            label="Satisfaction"
            value="—"
            :hint="data.quality.satisfactionAvailable ? 'Average rating' : 'Not collected yet'"
          />
        </div>
      </section>

      <section
        class="ticket-analytics__card ticket-analytics__card--wide"
        aria-labelledby="ticket-analytics-segment"
      >
        <h3 id="ticket-analytics-segment" class="ticket-analytics__card-title">
          Broken down by {{ dimensionLabel(dimension).toLowerCase() }}
        </h3>
        <!-- Without the roster every bar below falls back to "#11", which is
             the very thing this chart was fixed for, so the reason is put on
             the screen rather than left to be guessed at. Only while the
             assignee breakdown is the one showing: no other dimension reads
             the roster, and a warning about labels nobody is looking at is
             noise. -->
        <p
          v-if="dimension === 'assignee' && peopleFailed"
          class="ticket-analytics__error"
          role="alert"
        >
          The assignee list could not be loaded, so the bars below are labelled with user ids
          instead of names. Reload to try again.
        </p>
        <MeasureBars
          :label="`Broken down by ${dimensionLabel(dimension).toLowerCase()}`"
          :rows="segmentRows"
          unit="tickets"
        />
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import MeasureBars from '@/components/admin/tickets/analytics/MeasureBars.vue'
import StatTile from '@/components/admin/tickets/analytics/StatTile.vue'
import {
  channelLabel,
  describeWindow,
  dimensionLabel,
  duration,
  segmentLabel,
  windowProblem
} from '@/components/admin/tickets/analytics/analyticsFormat'
import { logApiError } from '@/utils/apiError'
import { fetchAssignees, fetchTicketAnalytics, wasRefused } from '@/utils/ticketAgentAPI'
import {
  TICKET_STATUS_LABELS,
  categoryLabel,
  type AssigneeOption,
  type TicketAnalytics,
  type TicketStatus
} from '@/utils/ticketAgentSchema'

const from = ref('')
const to = ref('')
// Always sent, so the payload's segment is never null in practice. Region
// first because the client's own screenshot has it selected.
const dimension = ref('region')

const data = ref<TicketAnalytics | null>(null)
const loading = ref(false)
const errorMessage = ref('')

// The roster the assignee breakdown turns owner ids into names with. Fetched
// once each time the page opens: there is no shared cache here to reuse the
// queue's copy, and a copy kept past a roster change is the staleness the
// React version had (T02).
const people = ref<AssigneeOption[]>([])
const peopleFailed = ref(false)

// Every date keystroke and every dimension change starts a request, and they
// can finish out of order. Only the newest may paint: an older answer landing
// last would put numbers on screen for a window the inputs no longer show.
let loadToken = 0

async function load() {
  const token = ++loadToken
  // Nothing keeps the previous numbers while the new ones load, as in React:
  // the cards blank until the answer for the window on screen arrives.
  data.value = null
  errorMessage.value = ''
  loading.value = true
  try {
    const result = await fetchTicketAnalytics({
      from: from.value,
      to: to.value,
      dimension: dimension.value
    })
    if (token !== loadToken) return
    data.value = result
  } catch (error) {
    if (token !== loadToken) return
    logApiError('ticket analytics', error)
    // A refusal is not a fault: both routes are gated on the server, and
    // "could not be loaded" would tell a reader who lacks access that the
    // product is broken. A 400 is the window the reader typed, and the
    // server's sentence says how to fix it. Anything else, a parse failure
    // included, gets the standing sentence.
    errorMessage.value = wasRefused(error)
      ? 'You do not have access to the ticket dashboard. It is open to the support team and to administrators.'
      : (windowProblem(error) ?? 'Those numbers could not be loaded.')
  } finally {
    if (token === loadToken) loading.value = false
  }
}

async function loadPeople() {
  try {
    people.value = await fetchAssignees()
    peopleFailed.value = false
  } catch (error) {
    logApiError('ticket analytics assignees', error)
    peopleFailed.value = true
  }
}

onMounted(() => {
  void load()
  void loadPeople()
})

// Retires whatever is still in flight, so nothing paints after the page
// has gone.
onBeforeUnmount(() => {
  loadToken += 1
})

watch([from, to, dimension], () => {
  void load()
})

const dimensionOptions = computed(() => data.value?.dimensions ?? [dimension.value])

const categoryRows = computed(() =>
  (data.value?.demand.categoryMix ?? []).map((bucket) => ({
    label: categoryLabel(bucket.value),
    value: bucket.count
  }))
)

const channelRows = computed(() =>
  (data.value?.demand.channelMix ?? []).map((bucket) => ({
    label: channelLabel(bucket.value),
    value: bucket.count
  }))
)

const ageRows = computed(() =>
  (data.value?.flow.ageByStatus ?? []).map((row) => ({
    label: TICKET_STATUS_LABELS[row.status as TicketStatus] ?? row.status,
    value: row.averageSeconds ?? 0
  }))
)

const segmentRows = computed(() =>
  (data.value?.segment?.buckets ?? []).map((bucket) => ({
    label: segmentLabel(dimension.value, bucket.value, people.value),
    value: bucket.count
  }))
)

// Null, not zero, for an empty window: nought percent resolved is a damning
// number to invent.
const resolvedShare = computed(() => {
  const rate = data.value?.quality.resolutionRate ?? null
  return rate === null ? '—' : `${Math.round(rate * 100)}%`
})
</script>

<style scoped>
/* The page ground is TicketsSection's .content-area, --bg-light, where
   --text-muted is 4.45:1 and --danger 4.30:1, both under AA. The literals are
   the ones TicketDetailPage.vue and TicketsSection.vue already use there
   (5.29:1 and 6.98:1). Dark hands both back to the theme, 6.19:1 and 6.58:1
   on its ground. Checked by analyticsContrast.spec.ts. */
.ticket-analytics {
  --analytics-muted: #616970;
  --analytics-danger: #a71d2a;

  display: flex;
  flex-direction: column;
  gap: 1rem;
}

:root[data-theme='dark'] .ticket-analytics {
  --analytics-muted: var(--text-muted);
  --analytics-danger: var(--danger);
}

/* The global focus ring is --dark-green, which the dark theme does not
   redefine: 2.79:1 on the dark card, under the 3:1 a focus indicator needs.
   The chart's "Show as a table" buttons sit on that card. */
:root[data-theme='dark'] .ticket-analytics :deep(:focus-visible) {
  outline-color: #5ea99e;
}

.ticket-analytics__title {
  margin: 0 0 0.25rem 0;
  font-size: 1.35rem;
  font-weight: 600;
}

.ticket-analytics__subtitle {
  margin: 0;
  color: var(--analytics-muted);
  font-size: 0.9rem;
}

.ticket-analytics__filters {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 0.75rem;
}

.ticket-analytics__field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.ticket-analytics__label {
  color: var(--charcoal);
  font-size: 0.8rem;
  font-weight: 600;
}

.ticket-analytics__input {
  width: 10rem;
  height: 2.25rem;
  padding: 0.25rem 0.5rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--white);
  color: var(--charcoal);
  font: inherit;
  font-size: 0.9rem;
}

.ticket-analytics__select {
  width: 12rem;
}

/* The date input's calendar glyph and the select's arrow are drawn by the
   browser, which only knows the theme through color-scheme. */
:root[data-theme='dark'] .ticket-analytics__input {
  color-scheme: dark;
}

.ticket-analytics__window {
  margin: -0.4rem 0 0 0;
  color: var(--analytics-muted);
  font-size: 0.8rem;
}

.ticket-analytics__loading {
  margin: 0;
  color: var(--analytics-muted);
  font-size: 0.9rem;
}

.ticket-analytics__error {
  margin: 0;
  color: var(--analytics-danger);
  font-size: 0.9rem;
}

.ticket-analytics__grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 1rem;
}

@media (min-width: 1024px) {
  .ticket-analytics__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .ticket-analytics__card--wide {
    grid-column: 1 / -1;
  }
}

.ticket-analytics__card {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  min-width: 0;
  padding: 1.25rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--white);
  box-shadow: 0 1px 2px var(--shadow);
}

.ticket-analytics__card-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
}

.ticket-analytics__chart-title {
  margin: 0 0 0.4rem 0;
  font-size: 0.875rem;
  font-weight: 600;
}

/* Three tiles to a row where they fit, fewer where they do not, rather than
   squeezing a nowrap value past the edge of its tile. */
.ticket-analytics__tiles {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(8.5rem, 1fr));
  gap: 0.5rem;
}
</style>
