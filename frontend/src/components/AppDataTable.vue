<template>
  <div class="data-table">
    <!-- Anything a page adds above the table, given its rows. -->
    <div v-if="$slots.toolbar" class="data-table-toolbar">
      <slot name="toolbar" :rows="filteredRows" :page-rows="pagedRows" :selected-rows="selectedRows" />
    </div>

    <div v-if="selectedCount && $slots.bulk" class="data-table-bulk">
      <p>{{ selectedCount }} selected</p>
      <slot name="bulk" :rows="selectedRows" :count="selectedCount" />
    </div>

    <!-- Search sits on top of the table, as on Group Marks. -->
    <div class="data-table-search-card">
      <label
        class="data-table-search-field"
        :style="searchWidth ? { flexBasis: searchWidth, maxWidth: searchWidth } : undefined"
      >
        <span class="data-table-search-label">Search</span>
        <span class="data-table-search-box">
          <i class="fas fa-magnifying-glass" aria-hidden="true"></i>
          <input
            v-model="search"
            class="data-table-search-input"
            type="search"
            :placeholder="searchPlaceholder"
          />
        </span>
      </label>
      <div v-if="$slots.filters" class="data-table-filters">
        <slot name="filters" />
      </div>
      <p v-if="$slots.stats" class="data-table-stats"><slot name="stats" /></p>
      <div v-if="$slots['search-side']" class="data-table-search-side">
        <slot name="search-side" />
      </div>
    </div>

    <div class="table-scroll-frame">
      <div
        ref="wrapEl"
        class="data-table-wrap table-scroll-box"
        :class="{ 'data-table-wrap--loading': loading }"
        @scroll="syncFromTable"
      >
        <table>
          <thead ref="headEl">
            <tr>
              <th class="data-table-check-col" scope="col" @click.stop>
                <input
                  type="checkbox"
                  :checked="allPageSelected"
                  :indeterminate.prop="somePageSelected"
                  :aria-label="allPageSelected ? 'Deselect this page' : 'Select this page'"
                  :disabled="loading || !pagedRows.length"
                  @change="togglePageSelection"
                />
              </th>
              <th v-if="hasDetail" class="data-table-expand-col" scope="col">
                <span class="sr-only">Details</span>
              </th>
              <th
                v-for="column in columns"
                :key="column.key"
                class="data-table-head"
                scope="col"
                :aria-sort="canSort(column) ? ariaSort(column.key) : undefined"
              >
                <button
                  v-if="canSort(column)"
                  type="button"
                  class="data-table-sort-btn"
                  @click="toggleSort(column.key)"
                >
                  {{ column.label }} <i class="fas" :class="sortIcon(column.key)" aria-hidden="true"></i>
                </button>
                <template v-else>{{ column.label }}</template>
              </th>
              <template v-if="$slots.actions">
                <th
                  v-for="index in actionColumns"
                  :key="`actions-${index}`"
                  class="data-table-head data-table-actions-col"
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
            <tr v-if="loading && !pagedRows.length">
              <td :colspan="emptyColspan" class="data-table-empty">Loading...</td>
            </tr>
            <tr v-else-if="!pagedRows.length">
              <td :colspan="emptyColspan" class="data-table-empty">{{ emptyMessage }}</td>
            </tr>
            <template v-for="row in pagedRows" :key="String(row[rowKey])">
              <tr
                class="data-table-row"
                :class="[{ 'data-table-row--clickable': clickableRows || hasDetail }, rowClass?.(row)]"
                @click="onRowClick(row)"
              >
                <td class="data-table-check-col" @click.stop>
                  <input
                    type="checkbox"
                    :checked="selectedIds.has(rowId(row))"
                    :aria-label="`Select ${displayCell(row, columns[0])}`"
                    :disabled="loading"
                    @change="toggleRow(row)"
                  />
                </td>
                <td v-if="hasDetail" class="data-table-expand-col" @click.stop>
                  <button
                    type="button"
                    class="data-table-expand-btn"
                    :aria-expanded="expandedIds.has(rowId(row))"
                    :aria-label="`${expandedIds.has(rowId(row)) ? 'Hide' : 'Show'} details for ${displayCell(row, columns[0])}`"
                    @click="toggleDetail(row)"
                  >
                    <i
                      class="fas"
                      :class="expandedIds.has(rowId(row)) ? 'fa-chevron-down' : 'fa-chevron-right'"
                      aria-hidden="true"
                    ></i>
                  </button>
                </td>
                <td
                  v-for="column in columns"
                  :key="column.key"
                  :class="{ 'data-table-cell--wrap': column.wrap }"
                >
                  <!-- A page can draw a cell itself with a cell-<key> slot. -->
                  <slot :name="`cell-${column.key}`" :row="row" :value="row[column.key]">
                    <RouterLink
                      v-if="columnLink(row, column)"
                      :to="columnLink(row, column)!"
                      class="data-table-link"
                    >
                      {{ displayCell(row, column) }}
                    </RouterLink>
                    <template v-else>{{ displayCell(row, column) }}</template>
                  </slot>
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
              <tr v-if="hasDetail && expandedIds.has(rowId(row))" class="data-table-detail-row">
                <td :colspan="emptyColspan">
                  <slot name="row-detail" :row="row" />
                </td>
              </tr>
            </template>
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
          <option v-for="size in sizeOptions" :key="size" :value="size">
            {{ size === DATA_TABLE_ALL ? 'All' : `${size} / page` }}
          </option>
        </select>
      </label>
      <p class="data-table-summary">{{ summaryText }}</p>
      <!-- The admin tables' pager, with the page number typed in. -->
      <nav class="data-table-pager" aria-label="Pages">
        <span class="data-table-page-info">Page {{ page }} of {{ totalPages }}</span>
        <button
          type="button"
          class="data-table-page-btn"
          :disabled="page <= 1 || loading"
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
          :disabled="page >= totalPages || loading"
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
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, type RouteLocationRaw } from 'vue-router'
import { useTopScrollbar } from '@/composables/useTopScrollbar'
import {
  DATA_TABLE_ALL,
  DATA_TABLE_PAGE_SIZES,
  DATA_TABLE_ROW_HEIGHT,
  cellText,
  fitPageSize,
} from '@/utils/dataTable'

export type DataTableColumn = {
  key: string
  label: string
  type?: 'string' | 'number'
  // Long text that may wrap; every other cell stays on one line.
  wrap?: boolean
  // Off by default when the server sorts; on by default otherwise.
  sortable?: boolean
  linkTo?: (row: Record<string, unknown>) => RouteLocationRaw | null | undefined
}

export type DataTableSort = { key: string; direction: 'asc' | 'desc' }

type RowKey = string | number

const props = withDefaults(
  defineProps<{
    columns: DataTableColumn[]
    rows: Record<string, unknown>[]
    rowKey?: string
    // How many columns the actions slot fills; the slot is told which one.
    actionColumns?: number
    emptyMessage?: string
    searchPlaceholder?: string
    // Wider than the usual 252px, for a long placeholder.
    searchWidth?: string
    loading?: boolean
    // Rows that open something when clicked; emits row-click.
    clickableRows?: boolean
    rowClass?: (row: Record<string, unknown>) => string | Record<string, boolean> | undefined
    // Server mode: give the total and the table shows `rows` as the current
    // page, leaving search, sorting and paging to the page through the
    // v-models below.
    totalCount?: number
    page?: number
    pageSize?: number
    // Given, the page searches the rows itself, in either mode.
    search?: string
    // Given, the page sorts the rows itself, in either mode.
    sort?: DataTableSort
    // Ticked rows, when the page keeps track of them.
    selected?: RowKey[]
  }>(),
  {
    rowKey: 'id',
    actionColumns: 1,
    emptyMessage: 'No matching entries.',
    searchPlaceholder: 'Search',
    searchWidth: undefined,
    loading: false,
    clickableRows: false,
    rowClass: undefined,
    totalCount: undefined,
    page: undefined,
    pageSize: undefined,
    search: undefined,
    sort: undefined,
    selected: undefined,
  },
)

const emit = defineEmits<{
  'row-click': [row: Record<string, unknown>]
  'update:page': [page: number]
  'update:pageSize': [size: number]
  'update:search': [search: string]
  'update:sort': [sort: DataTableSort]
  'update:selected': [keys: RowKey[]]
}>()

const isServer = computed(() => props.totalCount !== undefined)
const pageSorts = computed(() => isServer.value || props.sort !== undefined)
const pageSearches = computed(() => isServer.value || props.search !== undefined)

// Each of these follows its prop when the page passes one, and tells the
// page when it changes here.
const search = ref(props.search ?? '')
const page = ref(props.page ?? 1)
const pageSize = ref(props.pageSize ?? fitPageSize())
const sortKey = ref(props.sort?.key ?? (isServer.value ? '' : props.columns[0]?.key || ''))
const sortDir = ref<'asc' | 'desc'>(props.sort?.direction ?? 'asc')
const pageDraft = ref(String(page.value))
const ownSelection = ref<Set<RowKey>>(new Set())

watch(() => props.search, (value) => { if (value !== undefined) search.value = value })
watch(() => props.page, (value) => { if (value !== undefined) page.value = value })
watch(() => props.pageSize, (value) => { if (value !== undefined) pageSize.value = value })
watch(() => props.sort, (value) => {
  if (!value) return
  sortKey.value = value.key
  sortDir.value = value.direction
})
watch(search, (value) => { if (value !== props.search) emit('update:search', value) })
watch(page, (value) => { if (value !== props.page) emit('update:page', value) })
watch(pageSize, (value) => { if (value !== props.pageSize) emit('update:pageSize', value) })

const rowId = (row: Record<string, unknown>) => row[props.rowKey] as RowKey

const canSort = (column: DataTableColumn) => column.sortable ?? !isServer.value

const columnLink = (row: Record<string, unknown>, column: DataTableColumn) => {
  const text = displayCell(row, column)
  if (!text || text === '—') return null
  return column.linkTo?.(row) ?? null
}

const displayCell = (row: Record<string, unknown>, column?: DataTableColumn) =>
  column ? cellText(row, column.key) : '—'

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
  if (isServer.value) return props.rows
  const query = pageSearches.value ? '' : search.value.trim().toLowerCase()
  const source = !query
    ? [...props.rows]
    : props.rows.filter((row) =>
        props.columns.some((column) =>
          displayCell(row, column).toLowerCase().includes(query),
        ),
      )

  if (pageSorts.value) return source
  const column = props.columns.find((item) => item.key === sortKey.value)
  source.sort((left, right) => compare(left, right, column) * (sortDir.value === 'asc' ? 1 : -1))
  return source
})

const total = computed(() => (isServer.value ? props.totalCount ?? 0 : filteredRows.value.length))

const showsAll = computed(() => pageSize.value === DATA_TABLE_ALL)

const totalPages = computed(() =>
  showsAll.value ? 1 : Math.max(1, Math.ceil(total.value / pageSize.value)),
)

const pagedRows = computed(() => {
  if (isServer.value) return props.rows
  if (showsAll.value) return filteredRows.value
  const start = (page.value - 1) * pageSize.value
  return filteredRows.value.slice(start, start + pageSize.value)
})

const slots = defineSlots<{
  actions?: (props: { row: Record<string, unknown>; column: number }) => unknown
  bulk?: (props: { rows: Record<string, unknown>[]; count: number }) => unknown
  // Anything a page adds above the table, given all its rows, this page's
  // rows and the ticked rows.
  toolbar?: (props: {
    rows: Record<string, unknown>[]
    pageRows: Record<string, unknown>[]
    selectedRows: Record<string, unknown>[]
  }) => unknown
  // Fields beside Search, such as filters.
  filters?: () => unknown
  // A line of counts in the middle of the search card.
  stats?: () => unknown
  // Buttons on the right of the search card.
  'search-side'?: () => unknown
  // A row's details, opened under it by its chevron or a click on the row.
  'row-detail'?: (props: { row: Record<string, unknown> }) => unknown
  [cell: `cell-${string}`]: (props: { row: Record<string, unknown>; value: unknown }) => unknown
}>()

const selectedIds = computed<Set<RowKey>>(() =>
  props.selected ? new Set(props.selected) : ownSelection.value,
)

const setSelection = (next: Set<RowKey>) => {
  if (props.selected) emit('update:selected', [...next])
  else ownSelection.value = next
}

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

const hasDetail = computed(() => Boolean(slots['row-detail']))
const expandedIds = ref<Set<RowKey>>(new Set())

const toggleDetail = (row: Record<string, unknown>) => {
  const next = new Set(expandedIds.value)
  const id = rowId(row)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expandedIds.value = next
}

const onRowClick = (row: Record<string, unknown>) => {
  if (hasDetail.value) toggleDetail(row)
  else if (props.clickableRows) emit('row-click', row)
}

const emptyColspan = computed(
  () => props.columns.length + 1 + (hasDetail.value ? 1 : 0) + (slots.actions ? props.actionColumns : 0),
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
  const selected = selectedCount.value ? ` (${selectedCount.value} selected)` : ''
  if (!total.value) return `0 - 0 out of 0${selected}`
  if (showsAll.value) return `1 - ${total.value} out of ${total.value}${selected}`
  const start = (page.value - 1) * pageSize.value + 1
  const end = Math.min(page.value * pageSize.value, total.value)
  return `${start} - ${end} out of ${total.value}${selected}`
})

// The server resets its own paging; here a new search or page size starts
// again at page 1, and a shorter list never leaves the table past its end.
watch([search, pageSize], () => {
  if (!isServer.value) page.value = 1
})

watch(page, (value) => {
  pageDraft.value = String(value)
})

watch(totalPages, (value) => {
  if (!isServer.value && page.value > value) page.value = value
})

watch(
  () => props.rows,
  (rows) => {
    if (props.selected) return
    const valid = new Set(rows.map(rowId))
    const next = new Set([...ownSelection.value].filter((id) => valid.has(id)))
    if (next.size !== ownSelection.value.size) ownSelection.value = next
  },
)

const sortIcon = (key: string) =>
  sortKey.value !== key ? 'fa-sort' : sortDir.value === 'asc' ? 'fa-sort-up' : 'fa-sort-down'
const ariaSort = (key: string) =>
  sortKey.value !== key ? 'none' : sortDir.value === 'asc' ? 'ascending' : 'descending'

const toggleSort = (key: string) => {
  const direction = sortKey.value === key && sortDir.value === 'asc' ? 'desc' : 'asc'
  sortKey.value = key
  sortDir.value = direction
  if (pageSorts.value) emit('update:sort', { key, direction })
}

// Until someone picks a size, a table not started on All keeps its page to the
// rows that fit in the window, judged by the tallest row it has shown, so the
// scrollbar under the headings stays away.
const fitting = ref(pageSize.value !== DATA_TABLE_ALL)
const fittedSize = ref(pageSize.value)
let tallestRow = DATA_TABLE_ROW_HEIGHT

const fitToWindow = () => {
  if (!fitting.value || !wrapEl.value) return
  wrapEl.value.querySelectorAll<HTMLElement>('tr.data-table-row').forEach((row) => {
    tallestRow = Math.max(tallestRow, row.offsetHeight)
  })
  const next = fitPageSize(tallestRow, headEl.value?.offsetHeight || undefined)
  fittedSize.value = next
  if (next !== pageSize.value) pageSize.value = next
}

watch(pagedRows, () => void nextTick(fitToWindow))
onMounted(() => {
  fitToWindow()
  window.addEventListener('resize', fitToWindow)
})
onBeforeUnmount(() => window.removeEventListener('resize', fitToWindow))

// 7, 15 and 30, the fitted size among them, then All.
const sizeOptions = computed(() => {
  const sizes = DATA_TABLE_PAGE_SIZES.filter((size) => size !== DATA_TABLE_ALL)
  if (fittedSize.value !== DATA_TABLE_ALL && !sizes.includes(fittedSize.value)) sizes.push(fittedSize.value)
  return [...sizes.sort((a, b) => a - b), DATA_TABLE_ALL]
})

const onPageSizeChange = (event: Event) => {
  fitting.value = false
  pageSize.value = Number((event.target as HTMLSelectElement).value)
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
  setSelection(next)
}

const togglePageSelection = () => {
  const next = new Set(selectedIds.value)
  if (allPageSelected.value) {
    pagedRows.value.forEach((row) => next.delete(rowId(row)))
  } else {
    pagedRows.value.forEach((row) => next.add(rowId(row)))
  }
  setSelection(next)
}
</script>

<style scoped>
.data-table-toolbar,
.data-table-bulk {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.data-table-toolbar {
  flex-wrap: wrap;
  margin-bottom: 0.75rem;
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
  /* 52px tall, with its line; more if it wraps in a narrow window. */
  min-height: 3.25rem;
  padding: 0.4rem 1rem;
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

/* Filters beside Search, each with a label like SEARCH's. */
.data-table-filters {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 0.75rem 1rem;
}

/* Centred between Search and the buttons, as on Group Marks. */
.data-table-stats {
  margin: 0 auto;
  color: var(--teal);
  font-size: 0.9rem;
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

.data-table-wrap--loading {
  opacity: 0.6;
  pointer-events: none;
}

.data-table-row--clickable {
  cursor: pointer;
}

.data-table-expand-col {
  width: 1%;
  padding-left: 0;
  padding-right: 0;
}

.data-table-expand-btn {
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
}

.data-table-expand-btn:hover {
  color: var(--dark-green);
}

/* A row's details, across the whole table under it. */
.data-table-detail-row td {
  padding: 1rem 1.25rem;
  white-space: normal;
  background: var(--bg-light);
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

tbody tr:not(.data-table-detail-row):hover td {
  background-color: var(--light-green);
  box-shadow: 1px 0 0 var(--light-green);
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

tbody tr:last-child td {
  border-bottom: none;
}

/* Every row at least 56px tall; taller when a cell needs it. */
.data-table-row > td {
  height: 3.5rem;
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
