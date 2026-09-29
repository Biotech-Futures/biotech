<template>
  <p v-if="rows.length === 0" class="measure-bars__empty">
    {{ emptyMessage ?? 'Nothing in this window.' }}
  </p>

  <div v-else class="measure-bars">
    <!-- The drawing is for the eye only. Everything it says is in the table
         below, which is where a screen reader reads it from, so the bars are
         hidden from assistive technology rather than read out twice. -->
    <div
      class="measure-bars__chart"
      aria-hidden="true"
      data-testid="measure-bars-chart"
    >
      <!-- Recessive: the grid is a reading aid, not a mark. -->
      <div class="measure-bars__grid" :style="{ gridRow: `1 / ${rows.length + 1}` }">
        <span
          v-for="tick in scale.ticks"
          :key="tick"
          class="measure-bars__gridline"
          :style="{ left: `${percent(tick)}%` }"
        ></span>
      </div>

      <template v-for="(row, index) in rows" :key="index">
        <span class="measure-bars__label" :style="{ gridRow: index + 1 }">{{ row.label }}</span>
        <span class="measure-bars__track" :style="{ gridRow: index + 1 }">
          <!-- Rounded at the data end only, anchored to the baseline. -->
          <span
            class="measure-bars__bar"
            data-testid="measure-bar"
            :style="{ width: `${percent(row.value)}%` }"
          ></span>
        </span>
        <!-- Printed beside every bar rather than kept for a hover tooltip,
             which React had: a tooltip is out of reach of a keyboard and a
             touch screen, and it is the same text either way. -->
        <span class="measure-bars__value" :style="{ gridRow: index + 1 }">{{ shown(row.value) }}</span>
      </template>

      <!-- The axis needs the formatter too, not just the tooltip and the
           table. Without it the durations chart ran "0 / 70000 / 140000 /
           210000 / 280000" in raw seconds while every other number on the
           same page read "33h 58m". -->
      <div class="measure-bars__axis" :style="{ gridRow: rows.length + 1 }">
        <span
          v-for="tick in scale.ticks"
          :key="tick"
          class="measure-bars__tick"
          data-testid="measure-tick"
          :style="{ left: `${percent(tick)}%` }"
          >{{ show(tick) }}</span
        >
      </div>
    </div>

    <!-- The same numbers without the chart. Identity is never colour-alone
         here anyway, but a table is what a screen reader and a printout can
         actually use.

         React put the table in a closed <details>, which also takes it out of
         the accessibility tree until somebody opens it. Here it is always in
         the tree and only hidden from the eye; "Show as a table" shows it to
         sighted readers too, so there is one table and nobody hears it
         twice. -->
    <button
      type="button"
      class="measure-bars__toggle"
      :aria-expanded="tableShown"
      :aria-controls="tableId"
      @click="tableShown = !tableShown"
    >
      <i
        class="fas fa-caret-right measure-bars__caret"
        :class="{ 'measure-bars__caret--open': tableShown }"
        aria-hidden="true"
      ></i>
      Show as a table
    </button>
    <div :id="tableId" :class="{ 'sr-only': !tableShown }" data-testid="measure-table">
      <table class="measure-bars__table">
        <caption class="sr-only">{{ label }}</caption>
        <tbody>
          <tr v-for="(row, index) in rows" :key="index">
            <th scope="row">{{ row.label }}</th>
            <td>{{ shown(row.value) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, useId } from 'vue'

import { niceScale } from './analyticsFormat'

type Row = { label: string; value: number }

/** A single-series horizontal bar chart, drawn with plain CSS.
 *
 *  Single series on purpose: every measure on this page is one quantity broken
 *  down by one dimension, so a second colour would encode nothing, and a
 *  chart that does not need colour to be read at all puts no burden of
 *  colourblind separation on anybody.
 *
 *  Horizontal because the labels are words: category names and statuses do not
 *  fit under a vertical axis without rotating them.
 *
 *  React drew this with recharts. The portal has no chart library and this
 *  page does not justify adding one (the client: "Don't focus on it"), so the
 *  bars are CSS widths on a grid. */
const props = defineProps<{
  rows: Row[]
  /** The chart's name, read out as the table's caption. */
  label: string
  /** Printed after the value beside each bar and in the table. */
  unit?: string
  format?: (value: number) => string
  emptyMessage?: string
}>()

const tableShown = ref(false)
const tableId = `measure-bars-${useId()}`

const show = computed(() => props.format ?? ((value: number) => String(value)))

// Rows arrive commonest first from the server ("a chart needs no further
// sorting"), so the order on screen is the order delivered.
const scale = computed(() => niceScale(Math.max(0, ...props.rows.map((row) => row.value))))

function percent(value: number): number {
  return (Math.max(0, value) / scale.value.top) * 100
}

function shown(value: number): string {
  return `${show.value(value)}${props.unit ? ` ${props.unit}` : ''}`
}
</script>

<style scoped>
/* One colour for every bar. #017151 is the brand green, 6.03:1 on the light
   card (--white, #ffffff). The dark theme does not redefine --dark-green and
   it is 2.79:1 on the dark card (#161f1d), under the 3:1 a chart mark needs,
   so dark takes the brand's mint instead: #5ea99e, 6.13:1 there. Literal
   values, checked by analyticsContrast.spec.ts. */
.measure-bars {
  --measure-bar: #017151;
  --measure-muted: #616970;
}

:root[data-theme='dark'] .measure-bars {
  --measure-bar: #5ea99e;
  --measure-muted: #8a9a96;
}

.measure-bars__empty {
  margin: 0;
  padding: 1.25rem 0;
  color: #616970;
  font-size: 0.875rem;
}

:root[data-theme='dark'] .measure-bars__empty {
  color: #8a9a96;
}

.measure-bars__chart {
  display: grid;
  /* Label, bar, value. React fixed the label column at 130px and recharts
     does not wrap tick text, so "Help with a student or group" could be cut
     off; here a long label wraps instead. */
  grid-template-columns: minmax(5rem, 9.5rem) minmax(0, 1fr) minmax(3.5rem, max-content);
  column-gap: 0.75rem;
  row-gap: 0.4rem;
  align-items: center;
  font-size: 0.8rem;
}

.measure-bars__label {
  grid-column: 1;
  color: var(--charcoal);
  line-height: 1.3;
  overflow-wrap: anywhere;
}

.measure-bars__track {
  grid-column: 2;
  position: relative;
  z-index: 1;
  display: block;
  height: 1.35rem;
}

.measure-bars__bar {
  display: block;
  height: 100%;
  background: var(--measure-bar);
  border-radius: 0 4px 4px 0;
}

.measure-bars__value {
  grid-column: 3;
  color: var(--charcoal);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  text-align: right;
}

.measure-bars__grid {
  grid-column: 2;
  position: relative;
  align-self: stretch;
}

.measure-bars__gridline {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 1px;
  background: var(--border-light);
}

.measure-bars__axis {
  grid-column: 2;
  position: relative;
  height: 1.2rem;
  border-top: 1px solid var(--border-light);
}

.measure-bars__tick {
  position: absolute;
  top: 0.15rem;
  transform: translateX(-50%);
  color: var(--measure-muted);
  font-size: 0.72rem;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.measure-bars__toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  margin-top: 0.5rem;
  padding: 0.15rem 0;
  border: none;
  background: none;
  color: var(--measure-muted);
  font: inherit;
  font-size: 0.8rem;
  cursor: pointer;
}

.measure-bars__toggle:hover {
  color: var(--charcoal);
  text-decoration: underline;
}

.measure-bars__caret {
  width: 0.6rem;
  transition: transform 0.15s ease;
}

.measure-bars__caret--open {
  transform: rotate(90deg);
}

.measure-bars__table {
  width: 100%;
  margin-top: 0.4rem;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.measure-bars__table th,
.measure-bars__table td {
  padding: 0.25rem 0;
  border-bottom: 1px solid var(--border-light);
  color: var(--charcoal);
}

.measure-bars__table tr:last-child th,
.measure-bars__table tr:last-child td {
  border-bottom: none;
}

.measure-bars__table th {
  font-weight: 400;
  text-align: left;
}

.measure-bars__table td {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

@media (prefers-reduced-motion: reduce) {
  .measure-bars__caret {
    transition: none;
  }
}
</style>
