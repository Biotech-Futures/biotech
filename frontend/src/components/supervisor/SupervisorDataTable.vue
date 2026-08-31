<template>
  <div class="supervisor-table">
    <div class="supervisor-table-toolbar">
      <div class="supervisor-table-toolbar-left">
        <label class="supervisor-table-label">
          Options
          <select class="supervisor-table-select" :value="optionChoice" @change="onOption">
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
            <optgroup label="Selection">
              <option value="select-page">Select this page</option>
              <option value="select-all">Select all matching</option>
              <option value="clear-selection" :disabled="!selectedCount">Clear selection</option>
            </optgroup>
            <optgroup label="View">
              <option value="print">Print table</option>
              <option value="refresh">Refresh data</option>
              <option value="reset">Reset table</option>
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
        <label class="supervisor-table-label">
          Show
          <input
            class="supervisor-table-page-size"
            type="number"
            min="1"
            :value="pageSizeDraft"
            @input="onPageSizeInput"
            @keydown.enter.prevent="applyPageSize"
          />
          entries
        </label>
      </div>
      <label class="supervisor-table-label supervisor-table-search">
        Search
        <input
          v-model="search"
          class="supervisor-table-search-input"
          type="search"
          placeholder="Search"
        />
      </label>
    </div>

    <div v-if="selectedCount" class="supervisor-table-bulk">
      <p>{{ selectedCount }} selected</p>
      <slot name="bulk" :rows="selectedRows" :count="selectedCount" />
    </div>

    <div class="supervisor-table-wrap">
      <table>
        <thead>
          <tr>
            <th class="supervisor-table-check-col" scope="col" @click.stop>
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
              @click="toggleSort(column.key)"
            >
              <span class="supervisor-table-head">
                <span>{{ column.label }}</span>
                <span class="supervisor-table-sort" aria-hidden="true">
                  <span :class="{ active: sortKey === column.key && sortDir === 'asc' }">▲</span>
                  <span :class="{ active: sortKey === column.key && sortDir === 'desc' }">▼</span>
                </span>
              </span>
            </th>
            <th v-if="$slots.actions" class="supervisor-table-actions-col" scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!pagedRows.length">
            <td :colspan="emptyColspan" class="supervisor-table-empty">No matching entries.</td>
          </tr>
          <tr v-for="row in pagedRows" :key="String(row[rowKey])">
            <td class="supervisor-table-check-col" @click.stop>
              <input
                type="checkbox"
                :checked="selectedIds.has(rowId(row))"
                :aria-label="`Select ${displayCell(row, columns[0])}`"
                @change="toggleRow(row)"
              />
            </td>
            <td v-for="column in columns" :key="column.key">
              <RouterLink
                v-if="columnLink(row, column)"
                :to="columnLink(row, column)!"
                class="supervisor-table-link"
              >
                {{ displayCell(row, column) }}
              </RouterLink>
              <template v-else>{{ displayCell(row, column) }}</template>
            </td>
            <td v-if="$slots.actions" class="supervisor-table-actions-col" @click.stop>
              <slot name="actions" :row="row" />
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="supervisor-table-footer">
      <p class="supervisor-table-summary">{{ summaryText }}</p>
      <div class="supervisor-table-pager">
        <button type="button" class="btn btn-outline" :disabled="page <= 1" @click="page -= 1">
          Previous
        </button>
        <label class="supervisor-table-label">
          Page
          <input
            class="supervisor-table-page-jump"
            type="number"
            min="1"
            :max="totalPages"
            :value="pageDraft"
            @input="onPageDraftInput"
            @keydown.enter.prevent="jumpToPage"
          />
        </label>
        <button
          type="button"
          class="btn btn-outline"
          :disabled="page >= totalPages"
          @click="page += 1"
        >
          Next
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, type RouteLocationRaw } from 'vue-router'
import { printHtmlDocument } from '@/utils/consentDocument'

export type SupervisorColumn = {
  key: string
  label: string
  type?: 'string' | 'number'
  linkTo?: (row: Record<string, unknown>) => RouteLocationRaw | null | undefined
}

export type SupervisorTableOption = {
  value: string
  label: string
  needsSelection?: boolean
}

export type SupervisorTableOptionGroup = {
  label: string
  options: SupervisorTableOption[]
}

const props = withDefaults(
  defineProps<{
    columns: SupervisorColumn[]
    rows: Record<string, unknown>[]
    rowKey?: string
    filename?: string
    extraOptionGroups?: SupervisorTableOptionGroup[]
  }>(),
  { rowKey: 'id', filename: 'registered-students', extraOptionGroups: () => [] },
)

const emit = defineEmits<{
  refresh: []
  action: [value: string, rows: Record<string, unknown>[]]
}>()

const search = ref('')
const page = ref(1)
const pageSize = ref(10)
const pageSizeDraft = ref('10')
const pageDraft = ref('1')
const sortKey = ref(props.columns[0]?.key || '')
const sortDir = ref<'asc' | 'desc'>('asc')
const optionChoice = ref('')
const selectedIds = ref<Set<string>>(new Set())

const rowId = (row: Record<string, unknown>) => String(row[props.rowKey] ?? '')

const columnLink = (row: Record<string, unknown>, column: SupervisorColumn) => {
  const text = displayCell(row, column)
  if (!text || text === '—') return null
  return column.linkTo?.(row) ?? null
}

const displayCell = (row: Record<string, unknown>, column: SupervisorColumn) => {
  const value = row[column.key]
  if (Array.isArray(value)) return value.map((item) => String(item ?? '').trim()).filter(Boolean).join(', ') || '—'
  const text = String(value ?? '').trim()
  return text || '—'
}

const compare = (
  left: Record<string, unknown>,
  right: Record<string, unknown>,
  column?: SupervisorColumn,
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
  actions?: (props: { row: Record<string, unknown> }) => unknown
  bulk?: (props: { rows: Record<string, unknown>[]; count: number }) => unknown
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

const emptyColspan = computed(() => props.columns.length + 1 + (slots.actions ? 1 : 0))

const summaryText = computed(() => {
  const total = filteredRows.value.length
  const selected = selectedCount.value ? ` (${selectedCount.value} selected)` : ''
  if (!total) return `Showing 0 to 0 of 0 entries${selected}`
  const start = (page.value - 1) * pageSize.value + 1
  const end = Math.min(page.value * pageSize.value, total)
  return `Showing ${start} to ${end} of ${total} entries${selected}`
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

const toggleSort = (key: string) => {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
    return
  }
  sortKey.value = key
  sortDir.value = 'asc'
}

const applyPageSize = () => {
  const next = Math.max(1, Math.floor(Number(pageSizeDraft.value) || 10))
  pageSize.value = next
  pageSizeDraft.value = String(next)
}

const onPageSizeInput = (event: Event) => {
  pageSizeDraft.value = (event.target as HTMLInputElement).value
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

const csvEscape = (value: string) => `"${value.replaceAll('"', '""')}"`

const escapeHtml = (value: string) =>
  value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')

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
  const emails = rows.flatMap((row) => [row.email, row.pgEmail]).map((value) => String(value ?? '').trim())
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

const resetTable = () => {
  search.value = ''
  pageSize.value = 10
  pageSizeDraft.value = '10'
  page.value = 1
  sortKey.value = props.columns[0]?.key || ''
  sortDir.value = 'asc'
  selectedIds.value = new Set()
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
  if (value === 'select-page') {
    const next = new Set(selectedIds.value)
    pagedRows.value.forEach((row) => next.add(rowId(row)))
    selectedIds.value = next
  }
  if (value === 'select-all') selectedIds.value = new Set(filteredRows.value.map(rowId))
  if (value === 'clear-selection') selectedIds.value = new Set()
  if (value === 'print') printRows(filteredRows.value)
  if (value === 'refresh') emit('refresh')
  if (value === 'reset') resetTable()
  if (extraOptionValues.value.has(value)) {
    const option = props.extraOptionGroups
      .flatMap((group) => group.options)
      .find((item) => item.value === value)
    emit('action', value, option?.needsSelection ? selectedRows.value : filteredRows.value)
  }
}
</script>

<style scoped>
.supervisor-table-toolbar,
.supervisor-table-footer,
.supervisor-table-toolbar-left,
.supervisor-table-pager,
.supervisor-table-head,
.supervisor-table-sort,
.supervisor-table-bulk {
  display: flex;
  align-items: center;
}

.supervisor-table-toolbar {
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.75rem;
  flex-wrap: wrap;
}

.supervisor-table-toolbar-left,
.supervisor-table-pager,
.supervisor-table-head,
.supervisor-table-bulk {
  gap: 0.75rem;
}

.supervisor-table-label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  color: #6c757d;
  font-size: 0.9rem;
}

.supervisor-table-select,
.supervisor-table-page-size,
.supervisor-table-search-input,
.supervisor-table-page-jump {
  padding: 0.4rem 0.55rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  color: var(--charcoal);
  background: var(--white);
}

.supervisor-table-page-size,
.supervisor-table-page-jump {
  width: 4.5rem;
}

.supervisor-table-search-input {
  min-width: 12rem;
}

.supervisor-table-bulk {
  flex-wrap: wrap;
  margin-bottom: 0.75rem;
  padding: 0.55rem 0.75rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: #f6f8f6;
}

.supervisor-table-bulk p {
  margin: 0;
  color: #6c757d;
  font-size: 0.9rem;
}

.supervisor-table-wrap {
  overflow-x: auto;
  border: 1px solid var(--border-light);
  border-radius: 8px;
}

table {
  width: 100%;
  border-collapse: collapse;
}

th,
td {
  padding: 0.75rem 0.9rem;
  text-align: left;
  border-bottom: 1px solid var(--border-light);
  vertical-align: top;
}

th {
  cursor: pointer;
  background: #f6f8f6;
  user-select: none;
}

.supervisor-table-check-col,
.supervisor-table-actions-col {
  cursor: default;
  width: 1%;
  white-space: nowrap;
}

.supervisor-table-sort {
  flex-direction: column;
  gap: 0;
  margin-left: auto;
  font-size: 0.55rem;
  line-height: 1;
  color: #c5c9c5;
}

.supervisor-table-sort .active {
  color: var(--charcoal);
}

.supervisor-table-empty {
  color: #6c757d;
  text-align: center;
}

.supervisor-table-link {
  color: var(--dark-green);
  font-weight: 600;
  text-decoration: underline;
}

.supervisor-table-link:hover {
  color: #015940;
}

.supervisor-table-footer {
  justify-content: space-between;
  gap: 1rem;
  margin-top: 0.75rem;
  flex-wrap: wrap;
}

.supervisor-table-summary {
  margin: 0;
  color: #6c757d;
  font-size: 0.9rem;
}

.supervisor-table-head {
  width: 100%;
  justify-content: space-between;
}

@media (max-width: 720px) {
  .supervisor-table-search-input {
    min-width: 0;
    width: 100%;
  }
}
</style>
