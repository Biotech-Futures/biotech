import { computed, onBeforeUnmount, ref, watch } from 'vue'
import {
  downloadSystemLogs,
  fetchSystemLogs,
  type SystemLogExportType,
  type SystemLogFilterParams,
  type SystemLogRow
} from '@/utils/adminAPI'
import { logApiError } from '@/utils/apiError'
import { fitPageSize, serverPageLimit } from '@/utils/dataTable'
import { formatTimeZoneLabel, getSetTimeZone, zonedDayBoundary } from '@/utils/date'

/** The System Logs filters as the page holds them: days as picked
 *  ("YYYY-MM-DD"), empty for "any". */
export interface SystemLogFilters {
  fromDate: string
  toDate: string
  level: string
  source: string
  user: string
  requestId: string
}

export type SystemLogFilterField = keyof SystemLogFilters

export const defaultSystemLogFilters = (): SystemLogFilters => ({
  fromDate: '',
  toDate: '',
  level: '',
  source: '',
  user: '',
  requestId: ''
})

/** The API query the filters and search stand for. Picked days become the
 *  first and last millisecond of those days in the admin's own timezone, as
 *  ISO datetimes with that day's offset (the backend reads them as given). */
export function systemLogQuery(
  filters: SystemLogFilters,
  search = '',
  timeZone = getSetTimeZone()
): SystemLogFilterParams {
  const text = (value: string) => value.trim() || undefined
  return {
    from: (filters.fromDate && zonedDayBoundary(filters.fromDate, 'start', timeZone)) || undefined,
    to: (filters.toDate && zonedDayBoundary(filters.toDate, 'end', timeZone)) || undefined,
    level: filters.level || undefined,
    source: text(filters.source),
    user: text(filters.user),
    q: text(search),
    request_id: text(filters.requestId)
  }
}

export function useAdminSystemLogs() {
  const rows = ref<SystemLogRow[]>([])
  const totalCount = ref(0)
  const page = ref(1)
  const pageSize = ref(fitPageSize())
  const loading = ref(false)
  const error = ref('')
  const exporting = ref<SystemLogExportType | null>(null)
  const exportError = ref('')

  // -- Search (debounced, as on the users page) --------------------------------
  const searchInput = ref('')
  const appliedSearch = ref('')
  let searchTimer: ReturnType<typeof setTimeout> | null = null

  const cancelPendingSearch = () => {
    if (searchTimer) clearTimeout(searchTimer)
    searchTimer = null
  }

  watch(searchInput, (value) => {
    cancelPendingSearch()
    // Nothing to ask for when the search wouldn't change (spaces only, or
    // cleared along with the filters).
    if (value.trim() === appliedSearch.value) return
    searchTimer = setTimeout(() => {
      appliedSearch.value = value.trim()
      reloadFromFirstPage()
    }, 350)
  })

  onBeforeUnmount(cancelPendingSearch)

  // -- Filters -----------------------------------------------------------------
  const filters = ref<SystemLogFilters>(defaultSystemLogFilters())

  const query = computed(() => systemLogQuery(filters.value, appliedSearch.value))

  const hasActiveFilters = computed(
    () => Object.values(filters.value).some((value) => value.trim()) || Boolean(appliedSearch.value)
  )

  // "YYYY-MM-DD" strings compare in date order.
  const dateRangeError = computed(() =>
    filters.value.fromDate && filters.value.toDate && filters.value.fromDate > filters.value.toDate
      ? 'The "From" date is after the "To" date.'
      : ''
  )

  // The zone times are shown in, and picked days are read in.
  const timeZoneLabel = computed(() => formatTimeZoneLabel(getSetTimeZone()))

  // -- Loading -----------------------------------------------------------------
  // Only the latest request may fill the table, however the replies arrive.
  let latestRequest = 0

  const load = async () => {
    if (dateRangeError.value) {
      // A request still on its way is for filters no longer shown: it must
      // not fill the table under the error.
      latestRequest += 1
      loading.value = false
      rows.value = []
      totalCount.value = 0
      return
    }
    const request = ++latestRequest
    loading.value = true
    error.value = ''
    try {
      const data = await fetchSystemLogs({
        ...query.value,
        page: page.value,
        page_size: serverPageLimit(pageSize.value)
      })
      if (request !== latestRequest) return
      rows.value = data.results ?? []
      totalCount.value = data.count ?? 0
    } catch (loadError) {
      if (request !== latestRequest) return
      logApiError('admin.systemLogs.list', loadError)
      error.value = loadError instanceof Error ? loadError.message : 'System logs could not be loaded right now.'
      rows.value = []
      totalCount.value = 0
    } finally {
      if (request === latestRequest) loading.value = false
    }
  }

  const reloadFromFirstPage = () => {
    page.value = 1
    void load()
  }

  const applyFilterPatch = ({ field, value }: { field: SystemLogFilterField; value: string }) => {
    if (filters.value[field] === value) return
    filters.value = { ...filters.value, [field]: value }
    reloadFromFirstPage()
  }

  // One request: the search is cleared before its box, so the box's watcher
  // has nothing to ask for, and any search still waiting is dropped.
  const clearFilters = () => {
    cancelPendingSearch()
    filters.value = defaultSystemLogFilters()
    appliedSearch.value = ''
    searchInput.value = ''
    reloadFromFirstPage()
  }

  const onPageChange = (next: number) => {
    page.value = next
    void load()
  }

  const onPageSizeChange = (size: number) => {
    pageSize.value = size
    reloadFromFirstPage()
  }

  // -- Export ------------------------------------------------------------------
  const exportLogs = async (type: SystemLogExportType) => {
    if (exporting.value || dateRangeError.value) return
    exporting.value = type
    exportError.value = ''
    try {
      await downloadSystemLogs(query.value, type)
    } catch (downloadError) {
      logApiError('admin.systemLogs.export', downloadError)
      exportError.value =
        downloadError instanceof Error ? downloadError.message : 'The logs could not be exported right now.'
    } finally {
      exporting.value = null
    }
  }

  const emptyMessage = computed(() => {
    if (dateRangeError.value) return 'Choose a "From" date on or before the "To" date.'
    return hasActiveFilters.value ? 'No logs match these filters.' : 'No logs have been recorded yet.'
  })

  return {
    rows,
    totalCount,
    page,
    pageSize,
    loading,
    error,
    exporting,
    exportError,
    searchInput,
    filters,
    hasActiveFilters,
    dateRangeError,
    timeZoneLabel,
    emptyMessage,
    load,
    applyFilterPatch,
    clearFilters,
    onPageChange,
    onPageSizeChange,
    exportLogs
  }
}
