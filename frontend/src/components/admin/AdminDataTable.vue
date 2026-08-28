<template>
  <div class="admin-table">
    <div class="admin-table__scroll" :class="{ 'admin-table__scroll--loading': loading }">
      <table class="admin-table__table">
        <thead>
          <tr>
            <th v-if="selectable" class="admin-table__check">
              <input
                type="checkbox"
                :checked="allPageSelected"
                :indeterminate.prop="somePageSelected"
                :aria-label="selectAllLabel"
                :disabled="loading || !rows.length"
                @change="toggleSelectAllPage"
              />
            </th>
            <th
              v-for="column in columns"
              :key="column.key"
              :class="[
                `admin-table__head admin-table__head--${column.align || 'left'}`,
                { 'admin-table__sortable': column.sortable }
              ]"
              :style="column.width ? { width: column.width } : undefined"
            >
              <template v-if="column.sortable">
                <button
                  type="button"
                  class="admin-table__sort-btn"
                  :class="{ 'admin-table__sort-btn--active': isColumnActive(column.key) }"
                  :aria-label="sortLabel(column)"
                  :aria-sort="ariaSort(column.key)"
                  @click="onColumnSort(column.key)"
                >
                  <span>{{ column.label }}</span>
                  <i
                    class="fas admin-table__sort-icon"
                    :class="sortIcon(column.key)"
                    aria-hidden="true"
                  ></i>
                </button>
              </template>
              <template v-else>
                <slot :name="`header-${column.key}`" :column="column">{{ column.label }}</slot>
              </template>
            </th>
          </tr>
        </thead>

        <tbody>
          <tr v-if="loading && !rows.length" class="admin-table__loading-row">
            <td :colspan="colspan">
              <div class="admin-table__state">
                <span class="admin-table__spinner" aria-hidden="true"></span>
                <span>Loading...</span>
              </div>
            </td>
          </tr>

          <tr
            v-else-if="!rows.length"
            class="admin-table__empty-row"
          >
            <td :colspan="colspan">
              <div class="admin-table__state">
                <slot name="empty">
                  <span>{{ emptyMessage }}</span>
                </slot>
              </div>
            </td>
          </tr>

          <tr
            v-for="(row, index) in currentRows"
            v-else
            :key="rowKeyOf(row)"
            class="admin-table__row"
            :class="{ 'admin-table__row--selected': isRowSelected(row) }"
            @click="onRowClick(row)"
          >
            <td v-if="selectable" class="admin-table__check" @click.stop>
              <input
                type="checkbox"
                :checked="isRowSelected(row)"
                :aria-label="`Select row ${index + 1}`"
                :disabled="loading"
                @change="onToggleRow(row)"
              />
            </td>
            <td
              v-for="column in columns"
              :key="column.key"
              :class="`admin-table__cell admin-table__cell--${column.align || 'left'}`"
            >
              <slot :name="`cell-${column.key}`" :row="row" :value="row[column.key]">
                {{ renderCell(row[column.key]) }}
              </slot>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div
      v-if="showPagination"
      class="admin-table__footer"
    >
      <div class="admin-table__footer-left">
        <label v-if="pageSizeOptions.length" class="admin-table__page-size">
          <span class="sr-only">Rows per page</span>
          <select
            :value="pageSize"
            :disabled="loading"
            @change="onPageSizeChange"
          >
            <option v-for="size in pageSizeOptions" :key="size" :value="size">
              {{ size }} / page
            </option>
          </select>
        </label>
        <span class="admin-table__page-info">
          Page {{ page }} of {{ totalPages }}
        </span>
      </div>

      <nav class="admin-table__pager" :aria-label="pagerLabel">
        <button
          type="button"
          class="admin-table__page-btn"
          :disabled="page <= 1 || loading"
          :aria-label="'Previous page'"
          @click="onPageChange(page - 1)"
        >
          <i class="fas fa-chevron-left" aria-hidden="true"></i>
        </button>
        <span class="admin-table__page-number">{{ page }}</span>
        <button
          type="button"
          class="admin-table__page-btn"
          :disabled="page >= totalPages || loading"
          :aria-label="'Next page'"
          @click="onPageChange(page + 1)"
        >
          <i class="fas fa-chevron-right" aria-hidden="true"></i>
        </button>
      </nav>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

export interface AdminColumn {
  key: string
  label: string
  sortable?: boolean
  align?: 'left' | 'right' | 'center'
  width?: string
}

export type SortDirection = 'asc' | 'desc'
export type SortState = { key: string; direction: SortDirection }

const props = withDefaults(
  defineProps<{
    columns: AdminColumn[]
    rows: Record<string, unknown>[]
    rowKey?: string
    loading?: boolean
    selectable?: boolean
    selected?: Array<string | number>
    sortState?: SortState
    showPagination?: boolean
    page?: number
    pageSize?: number
    totalCount?: number
    pageSizeOptions?: number[]
    emptyMessage?: string
    pagerLabel?: string
    selectAllLabel?: string
  }>(),
  {
    rowKey: 'id',
    loading: false,
    selectable: false,
    selected: () => [],
    sortState: undefined,
    showPagination: true,
    page: 1,
    pageSize: 25,
    totalCount: 0,
    pageSizeOptions: () => [25, 50, 100],
    emptyMessage: 'No records found.',
    pagerLabel: 'Table pagination',
    selectAllLabel: 'Select all rows on this page'
  }
)

const emit = defineEmits<{
  (e: 'update:selected', value: Array<string | number>): void
  (e: 'update:sort', value: SortState): void
  (e: 'page-change', page: number): void
  (e: 'page-size-change', size: number): void
  (e: 'row-click', row: Record<string, unknown>): void
}>()

const colspan = computed(() => props.columns.length + (props.selectable ? 1 : 0))
const currentRows = computed(() => props.rows)
const totalPages = computed(() => Math.max(1, Math.ceil((props.totalCount ?? props.rows.length) / (props.pageSize || 1))))

const rowKeyOf = (row: Record<string, unknown>) => {
  const value = row[props.rowKey]
  return value as string | number
}

const selectedSet = computed(() => new Set(props.selected))

const isRowSelected = (row: Record<string, unknown>) => selectedSet.value.has(rowKeyOf(row))

const currentPageKeys = computed(() => currentRows.value.map(rowKeyOf))

const allPageSelected = computed(() => {
  return (
    currentPageKeys.value.length > 0 &&
    currentPageKeys.value.every((key) => selectedSet.value.has(key))
  )
})

const somePageSelected = computed(() => {
  return currentPageKeys.value.some((key) => selectedSet.value.has(key))
})

const toggleSelectAllPage = () => {
  const keys = currentPageKeys.value
  const next = new Set(props.selected)
  if (allPageSelected.value) {
    keys.forEach((key) => next.delete(key))
  } else {
    keys.forEach((key) => next.add(key))
  }
  emit('update:selected', Array.from(next))
}

const onToggleRow = (row: Record<string, unknown>) => {
  const key = rowKeyOf(row)
  const next = new Set(props.selected)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  emit('update:selected', Array.from(next))
}

const onRowClick = (row: Record<string, unknown>) => {
  emit('row-click', row)
}

const isColumnActive = (key: string) => props.sortState?.key === key

const ariaSort = (key: string): 'ascending' | 'descending' | 'none' => {
  if (!isColumnActive(key)) return 'none'
  return props.sortState!.direction === 'asc' ? 'ascending' : 'descending'
}

const sortIcon = (key: string) => {
  if (!isColumnActive(key)) return 'fa-sort'
  return props.sortState!.direction === 'asc' ? 'fa-sort-up' : 'fa-sort-down'
}

const sortLabel = (column: AdminColumn) => {
  const direction = isColumnActive(column.key)
    ? props.sortState!.direction === 'asc'
      ? 'descending'
      : 'ascending'
    : 'ascending'
  return `Sort by ${column.label} ${direction}`
}

const onColumnSort = (key: string) => {
  const direction: SortDirection =
    isColumnActive(key) && props.sortState!.direction === 'asc' ? 'desc' : 'asc'
  emit('update:sort', { key, direction })
}

const onPageChange = (page: number) => emit('page-change', page)

const onPageSizeChange = (event: Event) => {
  const value = Number((event.target as HTMLSelectElement).value)
  emit('page-size-change', value)
}

const renderCell = (value: unknown) => {
  if (value === null || value === undefined) return ''
  return String(value)
}
</script>

<style scoped>
.admin-table {
  width: 100%;
  background-color: var(--white);
  border: 1px solid var(--border-light);
  border-radius: 10px;
  box-shadow: 0 1px 2px rgba(7, 17, 15, 0.03);
  overflow: hidden;
}

.admin-table__scroll {
  width: 100%;
  overflow-x: auto;
}

.admin-table__scroll--loading {
  opacity: 0.6;
  pointer-events: none;
}

.admin-table__table {
  width: 100%;
  border-collapse: collapse;
}

.admin-table__check {
  width: 42px;
  padding: 0.75rem;
  text-align: center;
}

.admin-table__check input[type='checkbox'] {
  width: 16px;
  height: 16px;
  cursor: pointer;
  accent-color: var(--dark-green);
}

.admin-table__head {
  padding: 0.85rem 1rem;
  text-align: left;
  font-weight: 600;
  color: var(--charcoal);
  background-color: var(--light-green);
  border-bottom: 2px solid var(--border-light);
  white-space: nowrap;
}

.admin-table__head--right {
  text-align: right;
}

.admin-table__head--center {
  text-align: center;
}

.admin-table__sort-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0;
  border: none;
  background: transparent;
  color: inherit;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}

.admin-table__sort-btn:hover,
.admin-table__sort-btn--active {
  color: var(--dark-green);
}

.admin-table__sort-icon {
  font-size: 0.8rem;
  color: #c0c8c4;
}

.admin-table__sort-btn--active .admin-table__sort-icon {
  color: var(--dark-green);
}

.admin-table__cell {
  padding: 0.75rem 1rem;
  color: var(--charcoal);
  border-bottom: 1px solid var(--border-light);
}

.admin-table__cell--right {
  text-align: right;
}

.admin-table__cell--center {
  text-align: center;
}

.admin-table__row {
  transition: background-color 0.15s ease;
}

.admin-table__row:hover {
  background-color: var(--light-green);
}

.admin-table__row--selected {
  background-color: rgba(1, 113, 81, 0.08);
}

.admin-table__loading-row td,
.admin-table__empty-row td {
  padding: 2.5rem 1rem;
}

.admin-table__state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.6rem;
  color: var(--text-muted);
}

.admin-table__spinner {
  width: 18px;
  height: 18px;
  border: 2px solid var(--border-light);
  border-top-color: var(--dark-green);
  border-radius: 50%;
  animation: admin-table-spin 0.8s linear infinite;
}

.admin-table__footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  border-top: 1px solid var(--border-light);
  background-color: var(--bg-light);
}

.admin-table__footer-left {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.9rem;
}

.admin-table__page-size select {
  padding: 0.35rem 0.5rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background-color: var(--white);
  color: var(--charcoal);
  font-size: 0.875rem;
}

.admin-table__page-info {
  font-size: 0.875rem;
  color: var(--text-muted);
}

.admin-table__pager {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.admin-table__page-btn {
  width: 32px;
  height: 32px;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--white);
  color: var(--charcoal);
  font-size: 0.8rem;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.18s ease, color 0.18s ease;
}

.admin-table__page-btn:hover:not(:disabled) {
  background-color: var(--light-green);
  color: var(--dark-green);
}

.admin-table__page-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.admin-table__page-number {
  min-width: 2rem;
  text-align: center;
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--charcoal);
}

@keyframes admin-table-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .admin-table__spinner {
    animation: none;
  }
}

@media (max-width: 640px) {
  .admin-table__footer {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
