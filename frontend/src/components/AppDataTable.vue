<template>
  <div class="data-table">
    <div class="data-table-toolbar">
      <div class="data-table-toolbar-left">
        <label class="data-table-label">
          Options
          <select class="data-table-select" :value="optionChoice" @change="onOption">
            <option value="">Select</option>
            <optgroup label="Export">
              <option value="csv-all">Export all matching (CSV)</option>
              <option value="csv-page">Export this page (CSV)</option>
              <option value="csv-selected" :disabled="!selectedCount">Export selected (CSV)</option>
            </optgroup>
            <optgroup label="Clipboard">
              <option value="copy-table">Copy table</option>
              <option value="copy-emails">Copy emails</option>
              <option value="copy-selected" :disabled="!selectedCount">Copy selected rows</option>
            </optgroup>
            <optgroup label="View">
              <option value="print">Print table</option>
            </optgroup>
            <optgroup
              v-for="group in extraOptionGroups"
              :key="group.label"
              :label="group.label"
            >
              <option
                v-for="option in group.options"
                :key="option.value"
                :value="option.value"
                :disabled="option.needsSelection && !selectedCount"
              >
                {{ option.label }}
              </option>
            </optgroup>
          </select>
        </label>
      </div>
    </div>

    <div v-if="selectedCount" class="data-table-bulk">
      <p>{{ selectedCount }} selected</p>
      <slot name="bulk" :rows="selectedRows" :count="selectedCount" />
    </div>

    <!-- Search sits on top of the table, as on Group Marks. -->
    <div class="data-table-search-card">
      <label class="data-table-search-field">
        <span class="data-table-search-label">Search</span>
        <span class="data-table-search-box">
          <i class="fas fa-magnifying-glass" aria-hidden="true"></i>
          <input
            v-model="search"
            class="data-table-search-input"
            type="search"
            placeholder="Search"
          />
        </span>
      </label>
      <div v-if="$slots['search-side']" class="data-table-search-side">
        <slot name="search-side" />
      </div>
    </div>

    <div class="table-scroll-frame">
      <div ref="wrapEl" class="data-table-wrap table-scroll-box" @scroll="syncFromTable">
        <table>
          <thead ref="headEl">
            <tr>
              <th class="data-table-check-col" scope="col" @click.stop>
                <input
                  type="checkbox"
                  :checked="allPageSelected"
                  :indeterminate.prop="somePageSelected"
                  :aria-label="allPageSelected ? 'Deselect this page' : 'Select this page'"
                  @change="togglePageSelection"
                />
              </th>
              <th
                v-for="column in columns"
                :key="column.key"
                scope="col"
                :aria-sort="ariaSort(column.key)"
              >
                <button type="button" class="data-table-sort-btn" @click="toggleSort(column.key)">
                  {{ column.label }} <i class="fas" :class="sortIcon(column.key)" aria-hidden="true"></i>
                </button>
              </th>
              <template v-if="$slots.actions">
                <th
                  v-for="index in actionColumns"
                  :key="`actions-${index}`"
                  class="data-table-actions-col"
                  scope="col"
                >
                  <!-- Button columns have no heading, but screen readers still hear one. -->
                  <span class="sr-only">Actions</span>
                </th>
              </template>
            </tr>
          </thead>
          <tbody>
            <!-- Room for the scrollbar laid over it, just under the headings. -->
            <tr v-if="showBar" class="table-scroll-gap" aria-hidden="true">
              <td :colspan="emptyColspan" :style="{ height: `${barHeight}px` }"></td>
            </tr>
            <tr v-if="!pagedRows.length">
              <td :colspan="emptyColspan" class="data-table-empty">No matching entries.</td>
            </tr>
            <tr v-for="row in pagedRows" :key="String(row[rowKey])">
              <td class="data-table-check-col" @click.stop>
                <input
                  type="checkbox"
                  :checked="selectedIds.has(rowId(row))"
                  :aria-label="`Select ${displayCell(row, columns[0])}`"
                  @change="toggleRow(row)"
                />
              </td>
              <td
                v-for="column in columns"
                :key="column.key"
                :class="{ 'data-table-cell--wrap': column.wrap }"
              >
                <RouterLink
                  v-if="columnLink(row, column)"
                  :to="columnLink(row, column)!"
                  class="data-table-link"
                >
                  {{ displayCell(row, column) }}
                </RouterLink>
                <template v-else>{{ displayCell(row, column) }}</template>
              </td>
              <template v-if="$slots.actions">
                <td
                  v-for="index in actionColumns"
                  :key="`actions-${index}`"
                  class="data-table-actions-col"
                  @click.stop
                >
                  <slot name="actions" :row="row" :column="index - 1" />
                </td>
              </template>
            </tr>
          </tbody>
        </table>
      </div>
      <div
        v-show="showBar"
        ref="topScrollEl"
        class="table-top-scroll"
        :style="{ top: `${barTop}px` }"
        @scroll="syncFromTop"
      >
        <div :style="{ width: `${contentWidth}px` }"></div>
      </div>
    </div>

    <!-- Rows per page, joined to the bottom of the table as the admin tables do. -->
    <div class="data-table-bottom">
      <label class="data-table-page-size">
        <span class="sr-only">Rows per page</span>
        <select :value="pageSize" @change="onPageSizeChange">
          <option v-for="size in PAGE_SIZES" :key="size" :value="size">{{ size }} / page</option>
        </select>
      </label>
      <p class="data-table-summary">{{ summaryText }}</p>
      <!-- The admin tables' pager, with the page number typed in. -->
      <nav class="data-table-pager" aria-label="Pages">
        <span class="data-table-page-info">Page {{ page }} of {{ totalPages }}</span>
        <button
          type="button"
          class="data-table-page-btn"
          :disabled="page <= 1"
          aria-label="Previous page"
          @click="page -= 1"
        >
          <i class="fas fa-chevron-left" aria-hidden="true"></i>
        </button>
        <input
          class="data-table-page-jump"
          type="text"
          inputmode="numeric"
          :aria-label="`Page, of ${totalPages}`"
          :value="pageDraft"
          @input="onPageDraftInput"
          @keydown.enter.prevent="jumpToPage"
          @blur="jumpToPage"
        />
        <button
          type="button"
          class="data-table-page-btn"
          :disabled="page >= totalPages"
          aria-label="Next page"
          @click="page += 1"
        >
          <i class="fas fa-chevron-right" aria-hidden="true"></i>
        </button>
      </nav>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, type RouteLocationRaw } from 'vue-router'
import { useTopScrollbar } from '@/composables/useTopScrollbar'
import { printHtmlDocument } from '@/utils/consentDocument'

export type DataTableColumn = {
  key: string
  label: string
  type?: 'string' | 'number'
  // Long text that may wrap; every other cell stays on one line.
  wrap?: boolean
  linkTo?: (row: Record<string, unknown>) => RouteLocationRaw | null | undefined
}

export type DataTableOption = {
  value: string
  label: string
  needsSelection?: boolean
}

export type DataTableOptionGroup = {
  label: string
  options: DataTableOption[]
}

const props = withDefaults(
  defineProps<{
    columns: DataTableColumn[]
    rows: Record<string, unknown>[]
    rowKey?: string
    filename?: string
    // Row fields Copy emails reads.
    emailKeys?: string[]
    extraOptionGroups?: DataTableOptionGroup[]
    // How many columns the actions slot fills; the slot is told which one.
    actionColumns?: number
  }>(),
  {
    rowKey: 'id',
    filename: 'table',
    emailKeys: () => ['email'],
    extraOptionGroups: () => [],
    actionColumns: 1,
  },
)

const emit = defineEmits<{
  action: [value: string, rows: Record<string, unknown>[]]
}>()

const search = ref('')
const page = ref(1)
const PAGE_SIZES = [7, 15, 30]
const pageSize = ref(PAGE_SIZES[0])
const pageDraft = ref('1')
const sortKey = ref(props.columns[0]?.key || '')
const sortDir = ref<'asc' | 'desc'>('asc')
const optionChoice = ref('')
const selectedIds = ref<Set<string>>(new Set())

const rowId = (row: Record<string, unknown>) => String(row[props.rowKey] ?? '')

const columnLink = (row: Record<string, unknown>, column: DataTableColumn) => {
  const text = displayCell(row, column)
  if (!text || text === '—') return null
  return column.linkTo?.(row) ?? null
}

const displayCell = (row: Record<string, unknown>, column: DataTableColumn) => {
  const value = row[column.key]
  if (Array.isArray(value)) return value.map((item) => String(item ?? '').trim()).filter(Boolean).join(', ') || '—'
  const text = String(value ?? '').trim()
  return text || '—'
}

const compare = (
  left: Record<string, unknown>,
  right: Record<string, unknown>,
  column?: DataTableColumn,
) => {
  if (!column) return 0
  if (column.type === 'number') {
    return (Number(left[column.key]) || 0) - (Number(right[column.key]) || 0)
  }
  return displayCell(left, column).localeCompare(displayCell(right, column), undefined, {
    numeric: true,
    sensitivity: 'base',
  })
}

const filteredRows = computed(() => {
  const query = search.value.trim().toLowerCase()
  const source = !query
    ? [...props.rows]
    : props.rows.filter((row) =>
        props.columns.some((column) =>
          displayCell(row, column).toLowerCase().includes(query),
        ),
      )

  const column = props.columns.find((item) => item.key === sortKey.value)
  source.sort((left, right) => compare(left, right, column) * (sortDir.value === 'asc' ? 1 : -1))
  return source
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredRows.value.length / pageSize.value)))

const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredRows.value.slice(start, start + pageSize.value)
})

const slots = defineSlots<{
  actions?: (props: { row: Record<string, unknown>; column: number }) => unknown
  bulk?: (props: { rows: Record<string, unknown>[]; count: number }) => unknown
  // Buttons on the right of the search card.
  'search-side'?: () => unknown
}>()

const selectedCount = computed(() => selectedIds.value.size)

const selectedRows = computed(() =>
  props.rows.filter((row) => selectedIds.value.has(rowId(row))),
)

const allPageSelected = computed(
  () => pagedRows.value.length > 0 && pagedRows.value.every((row) => selectedIds.value.has(rowId(row))),
)

const somePageSelected = computed(
  () => !allPageSelected.value && pagedRows.value.some((row) => selectedIds.value.has(rowId(row))),
)

const emptyColspan = computed(
  () => props.columns.length + 1 + (slots.actions ? props.actionColumns : 0),
)

const {
  wrapEl,
  headEl,
  topScrollEl,
  showBar,
  contentWidth,
  barTop,
  barHeight,
  syncFromTable,
  syncFromTop,
} = useTopScrollbar()

const summaryText = computed(() => {
  const total = filteredRows.value.length
  const selected = selectedCount.value ? ` (${selectedCount.value} selected)` : ''
  if (!total) return `0 - 0 out of 0${selected}`
  const start = (page.value - 1) * pageSize.value + 1
  const end = Math.min(page.value * pageSize.value, total)
  return `${start} - ${end} out of ${total}${selected}`
})

watch([search, pageSize], () => {
  page.value = 1
  pageDraft.value = '1'
})

watch(page, (value) => {
  pageDraft.value = String(value)
})

watch(totalPages, (value) => {
  if (page.value > value) page.value = value
})

watch(
  () => props.rows,
  (rows) => {
    const valid = new Set(rows.map(rowId))
    const next = new Set([...selectedIds.value].filter((id) => valid.has(id)))
    if (next.size !== selectedIds.value.size) selectedIds.value = next
  },
)

const sortIcon = (key: string) =>
  sortKey.value !== key ? 'fa-sort' : sortDir.value === 'asc' ? 'fa-sort-up' : 'fa-sort-down'
const ariaSort = (key: string) =>
  sortKey.value !== key ? 'none' : sortDir.value === 'asc' ? 'ascending' : 'descending'

const toggleSort = (key: string) => {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
    return
  }
  sortKey.value = key
  sortDir.value = 'asc'
}

const onPageSizeChange = (event: Event) => {
  pageSize.value = Number((event.target as HTMLSelectElement).value) || PAGE_SIZES[0]
}

const onPageDraftInput = (event: Event) => {
  pageDraft.value = (event.target as HTMLInputElement).value
}

const jumpToPage = () => {
  const next = Math.min(totalPages.value, Math.max(1, Math.floor(Number(pageDraft.value) || 1)))
  page.value = next
  pageDraft.value = String(next)
}

const toggleRow = (row: Record<string, unknown>) => {
  const next = new Set(selectedIds.value)
  const id = rowId(row)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selectedIds.value = next
}

const togglePageSelection = () => {
  const next = new Set(selectedIds.value)
  if (allPageSelected.value) {
    pagedRows.value.forEach((row) => next.delete(rowId(row)))
  } else {
    pagedRows.value.forEach((row) => next.add(rowId(row)))
  }
  selectedIds.value = next
}

const csvEscape = (value: string) => `"${value.replace(/"/g, '""')}"`

const escapeHtml = (value: string) =>
  value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')

const rowsToCsv = (rows: Record<string, unknown>[]) => {
  const header = props.columns.map((column) => column.label).join(',')
  const lines = rows.map((row) => props.columns.map((column) => csvEscape(displayCell(row, column))).join(','))
  return [header, ...lines].join('\n')
}

const downloadCsv = (rows: Record<string, unknown>[], suffix = '') => {
  const blob = new Blob([rowsToCsv(rows)], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${props.filename}${suffix}.csv`
  link.click()
  URL.revokeObjectURL(url)
}

const copyText = async (value: string) => {
  await navigator.clipboard.writeText(value)
}

const rowToTsv = (row: Record<string, unknown>) =>
  props.columns.map((column) => displayCell(row, column)).join('\t')

const emailsFromRows = (rows: Record<string, unknown>[]) => {
  const emails = rows
    .flatMap((row) => props.emailKeys.map((key) => row[key]))
    .map((value) => String(value ?? '').trim())
  return [...new Set(emails.filter(Boolean))]
}

const printRows = (rows: Record<string, unknown>[]) => {
  const header = props.columns.map((column) => `<th>${escapeHtml(column.label)}</th>`).join('')
  const body = rows
    .map(
      (row) =>
        `<tr>${props.columns.map((column) => `<td>${escapeHtml(displayCell(row, column))}</td>`).join('')}</tr>`,
    )
    .join('')
  printHtmlDocument(
    props.filename,
    `<style>body{font-family:Arial,sans-serif;padding:1.5rem}table{width:100%;border-collapse:collapse}
    th,td{border:1px solid #ccc;padding:0.5rem;text-align:left}th{background:#f6f8f6}</style>
    <h1>${escapeHtml(props.filename)}</h1>
    <table><thead><tr>${header}</tr></thead><tbody>${body}</tbody></table>`,
  )
}

const extraOptionValues = computed(
  () => new Set(props.extraOptionGroups.flatMap((group) => group.options.map((option) => option.value))),
)

const onOption = async (event: Event) => {
  const value = (event.target as HTMLSelectElement).value
  optionChoice.value = ''
  if (!value) return
  if (value === 'csv-all') downloadCsv(filteredRows.value)
  if (value === 'csv-page') downloadCsv(pagedRows.value, '-page')
  if (value === 'csv-selected') downloadCsv(selectedRows.value, '-selected')
  if (value === 'copy-table') await copyText([props.columns.map((column) => column.label).join('\t'), ...filteredRows.value.map(rowToTsv)].join('\n'))
  if (value === 'copy-emails') await copyText(emailsFromRows(filteredRows.value).join(', '))
  if (value === 'copy-selected') await copyText([props.columns.map((column) => column.label).join('\t'), ...selectedRows.value.map(rowToTsv)].join('\n'))
  if (value === 'print') printRows(filteredRows.value)
  if (extraOptionValues.value.has(value)) {
    const option = props.extraOptionGroups
      .flatMap((group) => group.options)
      .find((item) => item.value === value)
    emit('action', value, option?.needsSelection ? selectedRows.value : filteredRows.value)
  }
}
</script>

<style scoped>
.data-table-toolbar,
.data-table-toolbar-left,
.data-table-bulk {
  display: flex;
  align-items: center;
}

.data-table-toolbar {
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.75rem;
  flex-wrap: wrap;
}

.data-table-toolbar-left,
.data-table-bulk {
  gap: 0.75rem;
}

.data-table-label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  color: #6c757d;
  font-size: 0.9rem;
}

.data-table-select {
  padding: 0.4rem 0.55rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  color: var(--teal);
  background: var(--white);
}

.data-table-pager {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-left: auto;
}

.data-table-page-info {
  margin-right: 0.4rem;
  font-size: 0.875rem;
  color: var(--text-muted);
}

.data-table-page-btn,
.data-table-page-jump {
  height: 32px;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--white);
  color: var(--teal);
}

.data-table-page-btn {
  width: 32px;
  font-size: 0.8rem;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: border-color 0.18s ease, color 0.18s ease;
}

.data-table-page-btn:hover:not(:disabled) {
  border-color: var(--dark-green);
  color: var(--dark-green);
}

.data-table-page-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.data-table-page-jump {
  width: 2.75rem;
  text-align: center;
  font-size: 0.9rem;
  font-weight: 600;
  font-family: inherit;
}

.data-table-page-jump:focus {
  outline: none;
  border-color: var(--dark-green);
}

/* The admin tables' footer strip. */
.data-table-bottom {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.9rem;
  padding: 0.75rem 1rem;
  border: 1px solid var(--border-light);
  border-top: none;
  border-radius: 0 0 8px 8px;
  background-color: var(--light-green);
}

.data-table-page-size select {
  padding: 0.35rem 0.5rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background-color: var(--white);
  color: var(--teal);
  font-size: 0.875rem;
}

/* The search card and box from Group Marks on Select Finalists. */
.data-table-search-card {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 0.75rem 1rem;
  padding: 1rem;
  border: 1px solid var(--border-light);
  border-bottom: none;
  border-radius: 8px 8px 0 0;
  background: var(--white);
}

.data-table-search-side {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-left: auto;
}

.data-table-search-field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  flex: 0 1 252px;
  max-width: 252px;
}

.data-table-search-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.data-table-search-box {
  position: relative;
}

.data-table-search-box .fas {
  position: absolute;
  left: 0.65rem;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  font-size: 0.8rem;
  pointer-events: none;
}

.data-table-search-input {
  width: 100%;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  padding: 0.45rem 0 0.45rem 2rem;
  font-size: 0.9rem;
  font-family: inherit;
  background: var(--surface-elevated);
  color: var(--teal);
}

.data-table-search-input:focus {
  outline: none;
  border-color: var(--dark-green);
}

.data-table-bulk {
  flex-wrap: wrap;
  margin-bottom: 0.75rem;
  padding: 0.55rem 0.75rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: #fafafa;
}

.data-table-bulk p {
  margin: 0;
  color: #6c757d;
  font-size: 0.9rem;
}

/* The same table as Group Marks on Grading's Select Finalists. */
.data-table-wrap {
  overflow-x: auto;
  border: 1px solid var(--border-light);
  /* Joins the search card above it and the rows per page below it. */
  border-radius: 0;
  background: var(--surface-elevated);
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
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

tbody tr:hover {
  background-color: transparent;
}

tbody tr:hover td {
  background-color: var(--light-green);
  box-shadow: 1px 0 0 var(--light-green);
}

/* A Dark Green heading row, with white text. */
thead th {
  color: #fff;
  font-weight: 600;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

tbody tr:last-child td {
  border-bottom: none;
}

/* A header that sorts: the header's own look, and a pointer. */
.data-table-sort-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0;
  border: none;
  background: transparent;
  font: inherit;
  letter-spacing: inherit;
  text-transform: inherit;
  color: inherit;
  cursor: pointer;
}

.data-table-sort-btn .fas {
  font-size: 0.7rem;
  opacity: 0.6;
}

.data-table-cell--wrap {
  white-space: normal;
  min-width: 14rem;
}

.data-table-check-col,
.data-table-actions-col {
  cursor: default;
  width: 1%;
  white-space: nowrap;
}

/* Row buttons sit on the right, as Group Marks' Add and Open do. */
.data-table-actions-col {
  text-align: right;
}

.data-table-empty {
  color: var(--text-muted);
  text-align: center;
  padding: 1.5rem 0.75rem;
}

.data-table-link {
  color: var(--dark-green);
  font-weight: 600;
  text-decoration: underline;
}

.data-table-link:hover {
  color: #015940;
}

.data-table-summary {
  margin: 0;
  color: #6c757d;
  font-size: 0.9rem;
}

@media (max-width: 720px) {
  .data-table-search-field {
    flex-basis: 100%;
    max-width: none;
  }
}
</style>
