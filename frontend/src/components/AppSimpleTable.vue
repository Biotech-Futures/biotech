<template>
  <!-- AppDataTable's table with none of its controls: no search card above,
       no sorting on the headings and no rows-per-page strip below. For short
       tables shown whole. -->
  <div class="simple-table-wrap">
    <table :class="{ 'simple-table--fixed': hasWidths }">
      <!-- Set widths line columns up, e.g. across several tables. -->
      <colgroup v-if="hasWidths">
        <col
          v-for="column in columns"
          :key="column.key"
          :style="column.width ? { width: column.width } : undefined"
        />
        <col v-if="$slots.actions" />
      </colgroup>
      <thead>
        <tr>
          <th
            v-for="column in columns"
            :key="column.key"
            scope="col"
            :class="column.align && `simple-table-head--${column.align}`"
          >
            {{ column.label }}
          </th>
          <th v-if="$slots.actions" class="simple-table-actions-col" scope="col">
            <!-- Button columns have no heading, but screen readers still hear one. -->
            <span class="sr-only">Actions</span>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="!rows.length">
          <td :colspan="columnCount" class="simple-table-empty">{{ emptyMessage }}</td>
        </tr>
        <tr v-for="row in rows" :key="rowId(row)" class="simple-table-row">
          <td
            v-for="column in columns"
            :key="column.key"
            :class="{
              'simple-table-cell--wrap': column.wrap,
              [`simple-table-cell--${column.align}`]: Boolean(column.align),
            }"
          >
            <!-- A page can draw a cell itself with a cell-<key> slot. -->
            <div class="simple-table-cell">
              <slot :name="`cell-${column.key}`" :row="row" :value="row[column.key]">
                {{ cellText(row, column.key) }}
              </slot>
            </div>
          </td>
          <td v-if="$slots.actions" class="simple-table-actions-col">
            <div class="simple-table-actions">
              <slot name="actions" :row="row" />
            </div>
          </td>
        </tr>
      </tbody>
      <!-- Rows after the body, e.g. a subtotal. The page styles them. -->
      <tfoot v-if="$slots.foot">
        <slot name="foot" />
      </tfoot>
    </table>
  </div>
</template>

<script setup lang="ts">
import { computed, useSlots } from 'vue'
import { cellText } from '@/utils/dataTable'

export interface SimpleTableColumn {
  key: string
  label: string
  align?: 'left' | 'center' | 'right'
  // Long text: wraps at the column's own width.
  wrap?: boolean
  // Any CSS width, e.g. '9rem' or a custom property the page sets.
  width?: string
}

const props = withDefaults(
  defineProps<{
    columns: SimpleTableColumn[]
    rows: Record<string, unknown>[]
    rowKey?: string
    emptyMessage?: string
  }>(),
  {
    rowKey: 'id',
    emptyMessage: 'Nothing to show.',
  }
)

const slots = useSlots()

const hasWidths = computed(() => props.columns.some((column) => column.width))
const columnCount = computed(() => props.columns.length + (slots.actions ? 1 : 0))
const rowId = (row: Record<string, unknown>) => String(row[props.rowKey] ?? '')
</script>

<style scoped>
/* AppDataTable's table, with its own rounded outline since nothing joins it
   above or below. */
.simple-table-wrap {
  overflow-x: auto;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--surface-elevated);
  /* Lets a cell measure itself against the table's visible width (cqw). */
  container-type: inline-size;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

/* With set widths, every table gets the same columns whatever its text. */
.simple-table--fixed {
  table-layout: fixed;
}

th,
td {
  padding: 0.55rem 0.75rem;
  text-align: left;
  border-bottom: 1px solid var(--border-light);
  white-space: nowrap;
  vertical-align: middle;
}

/* A browser paints a row's colour cell by cell, and where a column's width
   falls between screen pixels a hairline of the white table behind shows
   between cells. Each cell's colour spills 1px into the next to cover it. */
thead th {
  background-color: var(--dark-green);
  box-shadow: 1px 0 0 var(--dark-green);
}

/* A Dark Green heading row, 50px tall, with white text. */
thead th {
  height: 3.125rem;
  color: #fff;
  font-weight: 600;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.simple-table-row:hover td {
  background-color: var(--light-green);
  box-shadow: 1px 0 0 var(--light-green);
}

tbody tr:last-child td {
  border-bottom: none;
}

/* Every row at least 56px tall; taller when a cell needs it. */
.simple-table-row > td {
  height: 3.5rem;
}

/* A cell stays on one line until it would be wider than the table's visible
   width, then wraps, so no cell is wider than the page shows. */
.simple-table-cell {
  width: max-content;
  max-width: 100cqw;
  white-space: normal;
}

/* A column of long text wraps at its own width. */
.simple-table-cell--wrap {
  white-space: normal;
  min-width: 14rem;
}

.simple-table-cell--wrap > .simple-table-cell {
  width: auto;
}

.simple-table-head--center,
.simple-table-cell--center {
  text-align: center;
}

.simple-table-head--right,
.simple-table-cell--right {
  text-align: right;
}

/* Row buttons sit on the right, 8px apart. */
.simple-table-actions-col {
  width: 1%;
  white-space: nowrap;
  text-align: right;
}

.simple-table-actions {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.simple-table-empty {
  color: var(--text-muted);
  text-align: center;
  padding: 1.5rem 0.75rem;
}
</style>
