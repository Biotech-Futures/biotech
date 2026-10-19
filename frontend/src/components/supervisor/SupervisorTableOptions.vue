<template>
  <label class="table-options">
    <span class="table-options__label">Options</span>
    <AppSelect
      class="table-options__select"
      :model-value="choice"
      :options="menuOptions"
      @update:model-value="onOption"
    />
  </label>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { DataTableColumn } from '@/components/AppDataTable.vue'
import AppSelect, { type AppSelectOption, type AppSelectValue } from '@/components/AppSelect.vue'
import { printHtmlDocument } from '@/utils/consentDocument'
import { cellText } from '@/utils/dataTable'

// The Options menu above the My Students tables: export, copy or print the
// rows the table shows, through its toolbar slot.
const props = defineProps<{
  columns: DataTableColumn[]
  // Every row matching the search, this page's rows, and the ticked rows.
  rows: Record<string, unknown>[]
  pageRows: Record<string, unknown>[]
  selectedRows: Record<string, unknown>[]
  filename: string
  // Row fields Copy emails reads.
  emailKeys: string[]
}>()

const choice = ref('')

// "Select" while nothing's chosen, then each action under its heading; the
// ones for ticked rows only once some are ticked.
const menuOptions = computed<AppSelectOption[]>(() => {
  const noneTicked = !props.selectedRows.length
  return [
    { value: '', label: 'Select' },
    { value: 'csv-all', label: 'Export all matching (CSV)', group: 'Export' },
    { value: 'csv-page', label: 'Export this page (CSV)', group: 'Export' },
    { value: 'csv-selected', label: 'Export selected (CSV)', group: 'Export', disabled: noneTicked },
    { value: 'copy-table', label: 'Copy table', group: 'Clipboard' },
    { value: 'copy-emails', label: 'Copy emails', group: 'Clipboard' },
    { value: 'copy-selected', label: 'Copy selected rows', group: 'Clipboard', disabled: noneTicked },
    { value: 'print', label: 'Print table', group: 'View' }
  ]
})

const csvEscape = (value: string) => `"${value.replace(/"/g, '""')}"`

const escapeHtml = (value: string) =>
  value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')

const rowsToCsv = (rows: Record<string, unknown>[]) => {
  const header = props.columns.map((column) => column.label).join(',')
  const lines = rows.map((row) => props.columns.map((column) => csvEscape(cellText(row, column.key))).join(','))
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
  props.columns.map((column) => cellText(row, column.key)).join('\t')

const tableText = (rows: Record<string, unknown>[]) =>
  [props.columns.map((column) => column.label).join('\t'), ...rows.map(rowToTsv)].join('\n')

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
        `<tr>${props.columns.map((column) => `<td>${escapeHtml(cellText(row, column.key))}</td>`).join('')}</tr>`,
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

// Each choice does its action, and the box goes back to "Select".
const onOption = async (value: AppSelectValue) => {
  choice.value = ''
  if (value === 'csv-all') downloadCsv(props.rows)
  if (value === 'csv-page') downloadCsv(props.pageRows, '-page')
  if (value === 'csv-selected') downloadCsv(props.selectedRows, '-selected')
  if (value === 'copy-table') await copyText(tableText(props.rows))
  if (value === 'copy-emails') await copyText(emailsFromRows(props.rows).join(', '))
  if (value === 'copy-selected') await copyText(tableText(props.selectedRows))
  if (value === 'print') printRows(props.rows)
}
</script>

<style scoped>
/* Laid out like the table's Search field beside it: a small capital label
   over a box of the same height. */
.table-options {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.table-options__label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.table-options__select {
  padding: 0.45rem 0.55rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  font-size: 0.9rem;
  font-family: inherit;
  color: var(--teal);
  background: var(--surface-elevated);
}
</style>
