import { computed, ref, watch, type Ref } from 'vue'
import { type AdminColumn, type SortState } from '@/components/admin/AdminDataTable.vue'
import { runAdminView, type AdminUser, type AdminView } from '@/utils/adminAPI'
import { logApiError } from '@/utils/apiError'

export type GroupByOption = 'none' | 'role' | 'status'

/** The `run/` endpoint's row shape (backend `_hydrate_users_by_ids` in
 *  apps/admin/services/views.py) includes a couple of fields not modeled on
 *  the shared AdminUser type the Users list uses. */
export type ViewResultRow = AdminUser & {
  matchedPartner?: string
  phone?: string
}

interface ColumnConfig {
  label: string
  /** Backend sort_by key (services/views.py `sort_map`); omitted when the column isn't sortable. */
  sortBy?: string
}

// Mirrors the backend's COLUMN_HEADER_MAP / _extract_column_value alias handling
// (backend/apps/admin/services/views.py) so a view's saved `visibleColumns` render
// consistently regardless of which spelling was used when the view was created.
const COLUMN_ALIASES: Record<string, string> = {
  full_name: 'name',
  institution: 'school',
  school_name: 'school',
  matched_partner: 'matched_mentor',
  last_login: 'lastlogin',
  year_level: 'yearlevel',
  year_lvl: 'yearlevel'
}

const COLUMN_CONFIG: Record<string, ColumnConfig> = {
  name: { label: 'Full Name', sortBy: 'name' },
  email: { label: 'Email', sortBy: 'email' },
  role: { label: 'Role', sortBy: 'role' },
  school: { label: 'School / Institution', sortBy: 'school' },
  matched_mentor: { label: 'Matched Mentor / Group' },
  status: { label: 'Status', sortBy: 'status' },
  phone: { label: 'Phone' },
  state: { label: 'State', sortBy: 'state' },
  country: { label: 'Country', sortBy: 'country' },
  interests: { label: 'Interests' },
  lastlogin: { label: 'Last Login', sortBy: 'lastLogin' },
  yearlevel: { label: 'Year Level', sortBy: 'yearLevel' },
  group: { label: 'Group', sortBy: 'group' }
}

/** Normalizes a saved column key to the canonical key used by COLUMN_CONFIG. */
export const canonicalColumnKey = (key: string): string => {
  const normalized = key.toLowerCase().trim().replace(/\s+/g, '_')
  return COLUMN_ALIASES[normalized] || normalized
}

export const columnLabel = (key: string): string => {
  const canonical = canonicalColumnKey(key)
  return COLUMN_CONFIG[canonical]?.label ?? canonical.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

const PAGE_SIZE_OPTIONS = [25, 50, 100]

export function useAdminViewExecuted(viewId: Ref<number>) {
  const view = ref<AdminView | null>(null)
  const rows = ref<ViewResultRow[]>([])
  const totalCount = ref(0)
  const loading = ref(false)
  const error = ref('')

  const page = ref(1)
  const limit = ref(25)
  const sortState = ref<SortState>({ key: 'name', direction: 'asc' })
  const groupBy = ref<GroupByOption>('none')

  const searchInput = ref('')
  const appliedSearch = ref('')
  let searchTimer: ReturnType<typeof setTimeout> | null = null

  watch(searchInput, (value) => {
    if (searchTimer) clearTimeout(searchTimer)
    searchTimer = setTimeout(() => {
      appliedSearch.value = value.trim()
      reload()
    }, 350)
  })

  const badgeLabel = computed(() => (view.value?.isDefault ? 'System Default' : 'Custom View'))

  const columns = computed<AdminColumn[]>(() =>
    (view.value?.visibleColumns ?? []).map((rawKey) => {
      const key = canonicalColumnKey(rawKey)
      const config = COLUMN_CONFIG[key]
      return {
        key,
        label: config?.label ?? columnLabel(rawKey),
        sortable: Boolean(config?.sortBy)
      }
    })
  )

  const emptyMessage = computed(() =>
    loading.value ? '' : `No users found${appliedSearch.value ? ' for the current search.' : '.'}`
  )

  const loadResults = async (): Promise<void> => {
    if (!Number.isFinite(viewId.value) || viewId.value <= 0) {
      error.value = 'Invalid view id.'
      return
    }

    loading.value = true
    error.value = ''
    try {
      const data = await runAdminView(viewId.value, {
        page: page.value,
        limit: limit.value,
        search: appliedSearch.value || undefined,
        sortBy: COLUMN_CONFIG[sortState.value.key]?.sortBy,
        sortOrder: sortState.value.direction,
        // Passed through for forward compatibility; the backend does not yet
        // group results by this param (see AdminViewRunView.get) — flagged to
        // Person 1. The control still narrows sort/columns correctly in the
        // meantime, it just won't visually group rows.
        groupBy: groupBy.value === 'none' ? undefined : groupBy.value
      })
      view.value = data.view
      rows.value = data.items
      totalCount.value = data.total
    } catch (err: unknown) {
      logApiError('admin.views.run', err)
      error.value = err instanceof Error ? err.message : 'View results could not be loaded.'
      rows.value = []
      totalCount.value = 0
    } finally {
      loading.value = false
    }
  }

  const reload = (): void => {
    page.value = 1
    void loadResults()
  }

  const onSortChange = (next: SortState): void => {
    sortState.value = next
    reload()
  }

  const onPageChange = (next: number): void => {
    page.value = next
    void loadResults()
  }

  const onPageSizeChange = (size: number): void => {
    limit.value = size
    page.value = 1
    void loadResults()
  }

  const onGroupByChange = (next: GroupByOption): void => {
    groupBy.value = next
    reload()
  }

  return {
    view,
    rows,
    totalCount,
    loading,
    error,
    page,
    limit,
    sortState,
    groupBy,
    searchInput,
    columns,
    emptyMessage,
    badgeLabel,
    pageSizeOptions: PAGE_SIZE_OPTIONS,
    loadResults,
    reload,
    onSortChange,
    onPageChange,
    onPageSizeChange,
    onGroupByChange
  }
}
