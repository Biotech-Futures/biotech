<template>
  <label class="table-options">
    Options
    <select class="table-options__select" :value="choice" @change="onOption">
      <option value="">Select</option>
      <optgroup label="Export">
        <option value="csv-all">Export all matching (CSV)</option>
        <option value="csv-page">Export this page (CSV)</option>
        <option value="csv-selected" :disabled="!selectedRows.length">Export selected (CSV)</option>
      </optgroup>
      <optgroup label="Clipboard">
        <option value="copy-table">Copy table</option>
        <option value="copy-emails">Copy emails</option>
        <option value="copy-selected" :disabled="!selectedRows.length">Copy selected rows</option>
      </optgroup>
      <optgroup label="View">
        <option value="print">Print table</option>
      </optgroup>
    </select>
  </label>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { DataTableColumn } from '@/components/AppDataTable.vue'
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

const onOption = async (event: Event) => {
  const value = (event.target as HTMLSelectElement).value
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
.table-options {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  color: #6c757d;
  font-size: 0.9rem;
}

.table-options__select {
  padding: 0.4rem 0.55rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  color: var(--teal);
  background: var(--white);
}
</style>
