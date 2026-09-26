import { computed, ref, watch, type Ref } from 'vue'
import { type AdminColumn, type SortState } from '@/components/admin/AdminDataTable.vue'
import {
  bulkDeleteUsers,
  bulkSetUsersActive,
  deleteAdminUser,
  fetchAdminCountries,
  fetchAdminStates,
  fetchAdminUsers,
  runAdminView,
  setAdminUserActive,
  type AdminUser,
  type AdminUserCountry,
  type AdminUserState,
  type AdminView
} from '@/utils/adminAPI'
import { logApiError } from '@/utils/apiError'
import { userName } from '@/utils/userFormat'

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
  const busy = ref(false)
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
      clearSelection()
      reload()
    }, 350)
  })

  const badgeLabel = computed(() => (view.value?.isDefault ? 'System Default' : 'Custom View'))

  const columns = computed<AdminColumn[]>(() => [
    ...(view.value?.visibleColumns ?? []).map((rawKey) => {
      const key = canonicalColumnKey(rawKey)
      const config = COLUMN_CONFIG[key]
      return {
        key,
        label: config?.label ?? columnLabel(rawKey),
        sortable: Boolean(config?.sortBy)
      }
    }),
    { key: 'actions', label: 'Actions', align: 'right' as const }
  ])

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
    clearSelection()
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
    clearSelection()
    reload()
  }

  // -- Row selection -----------------------------------------------------------
  // A snapshot map (not just ids) so bulk actions that need row data (e.g. group
  // assignment) keep working for selections that span multiple pages.
  const selectedMap = ref<Map<number, ViewResultRow>>(new Map())
  const selectedIds = computed(() => Array.from(selectedMap.value.keys()))
  const bulkCount = computed(() => selectedMap.value.size)

  // StudentAssignDialog / confirmStudentAssignments trust the caller completely —
  // the backend hardcodes membership_role='student' for every id it's given, with
  // no check that the user actually is one (see backend/apps/admin/services/match.py
  // confirm_student_assignments). A view's rows aren't guaranteed single-role like
  // the Users page's Students tab is, so this page has to enforce it client-side:
  // only allow the bulk assign action when the *actual selection* is all students.
  const canAssignToGroup = computed(
    () => selectedMap.value.size > 0 && Array.from(selectedMap.value.values()).every((u) => u.role === 'student')
  )

  const clearSelection = (): void => {
    selectedMap.value = new Map()
  }

  const onSelectedChange = (value: Array<string | number>): void => {
    const rowById = new Map(rows.value.map((row) => [row.id, row]))
    const next = new Map<number, ViewResultRow>()
    for (const id of value) {
      const numericId = Number(id)
      const existing = selectedMap.value.get(numericId)
      next.set(numericId, existing ?? rowById.get(numericId) ?? ({ id: numericId } as ViewResultRow))
    }
    selectedMap.value = next
  }

  // Keep selected snapshots current after a refetch (e.g. a bulk status change).
  watch(rows, (list) => {
    if (selectedMap.value.size === 0) return
    let changed = false
    const next = new Map(selectedMap.value)
    for (const row of list) {
      if (next.has(row.id)) {
        next.set(row.id, row)
        changed = true
      }
    }
    if (changed) selectedMap.value = next
  })

  // -- Detail sheet --------------------------------------------------------------
  const viewOpen = ref(false)
  const detailUser = ref<ViewResultRow | null>(null)

  const openView = (user: ViewResultRow): void => {
    detailUser.value = user
    viewOpen.value = true
  }

  const onViewClose = (): void => {
    viewOpen.value = false
    detailUser.value = null
  }

  const onRowClick = (row: Record<string, unknown>): void => {
    openView(row as unknown as ViewResultRow)
  }

  // -- Single activate/deactivate -------------------------------------------------
  const singleToggle = ref({ open: false, userId: 0, message: '' })

  const runActiveChange = async (userId: number, isActive: boolean): Promise<boolean> => {
    busy.value = true
    try {
      await setAdminUserActive(userId, isActive)
      void loadResults()
      return true
    } catch (toggleError) {
      logApiError('admin.views.toggle', toggleError)
      return false
    } finally {
      busy.value = false
    }
  }

  const onToggleActive = (user: ViewResultRow): void => {
    // Deactivating locks someone out, so confirm it; reactivating is non-destructive.
    if (user.isActive) {
      singleToggle.value = {
        open: true,
        userId: user.id,
        message: `${userName(user)} will no longer be able to sign in. You can reactivate them at any time.`
      }
      return
    }
    void runActiveChange(user.id, true)
  }

  const runSingleToggle = async (): Promise<void> => {
    if (!singleToggle.value.userId) return
    const ok = await runActiveChange(singleToggle.value.userId, false)
    if (ok) singleToggle.value = { open: false, userId: 0, message: '' }
  }

  // -- Single delete (reachable from the edit sheet's Delete button) --------------
  const singleDelete = ref<{ open: boolean; userId: number; message: string; force: boolean }>({
    open: false,
    userId: 0,
    message: '',
    force: false
  })
  const singleDeleteConfirmText = ref('')
  const singleDeleteConfirmBlocked = computed(
    () => singleDelete.value.force && singleDeleteConfirmText.value !== 'DELETE'
  )

  const runSingleDelete = async (): Promise<void> => {
    const userId = singleDelete.value.userId
    if (!userId) return
    busy.value = true
    try {
      await deleteAdminUser(userId, singleDelete.value.force)
      singleDelete.value = { open: false, userId: 0, message: '', force: false }
      singleDeleteConfirmText.value = ''
      onViewClose()
      clearSelection()
      void loadResults()
    } catch (deleteError) {
      logApiError('admin.views.delete', deleteError)
      error.value = deleteError instanceof Error ? deleteError.message : 'Unable to delete the user right now.'
    } finally {
      busy.value = false
    }
  }

  // -- Bulk activate/deactivate ----------------------------------------------------
  const bulkStatus = ref<{
    open: boolean
    action: 'activate' | 'deactivate'
    title: string
    message: string
    confirmLabel: string
  }>({ open: false, action: 'activate', title: '', message: '', confirmLabel: '' })

  const confirmBulkStatus = (isActive: boolean): void => {
    const action = isActive ? 'activate' : 'deactivate'
    bulkStatus.value = {
      open: true,
      action,
      confirmLabel: isActive ? 'Activate' : 'Deactivate',
      title: `${isActive ? 'Activate' : 'Deactivate'} ${bulkCount.value} ${bulkCount.value === 1 ? 'user' : 'users'}?`,
      message: isActive
        ? 'The selected users will be able to sign in again.'
        : 'The selected users will no longer be able to sign in. You can reactivate them at any time.'
    }
  }

  const runBulkStatus = async (): Promise<void> => {
    busy.value = true
    try {
      await bulkSetUsersActive({
        isActive: bulkStatus.value.action === 'activate',
        userIds: selectedIds.value
      })
      bulkStatus.value = { ...bulkStatus.value, open: false }
      clearSelection()
      void loadResults()
    } catch (bulkError) {
      logApiError('admin.views.bulk-status', bulkError)
    } finally {
      busy.value = false
    }
  }

  // -- Bulk delete -------------------------------------------------------------
  const bulkDelete = ref({ open: false })
  const bulkForce = ref(false)
  const deleteConfirmText = ref('')

  const bulkDeleteMessage = computed(
    () =>
      `This permanently removes the selected ${bulkCount.value === 1 ? 'account' : 'accounts'} and all related data. This cannot be undone.`
  )

  const deleteConfirmBlocked = computed(() => bulkForce.value && deleteConfirmText.value !== 'DELETE')

  const confirmBulkDelete = (): void => {
    bulkForce.value = false
    deleteConfirmText.value = ''
    bulkDelete.value = { open: true }
  }

  const runBulkDelete = async (): Promise<void> => {
    busy.value = true
    try {
      const result = await bulkDeleteUsers({
        userIds: selectedIds.value,
        force: bulkForce.value
      })
      bulkDelete.value = { open: false }
      clearSelection()
      void loadResults()
      if (result?.msg) error.value = result.msg
    } catch (bulkError) {
      logApiError('admin.views.bulk-delete', bulkError)
      error.value =
        bulkError instanceof Error ? bulkError.message : 'Unable to delete the selected users right now.'
    } finally {
      busy.value = false
    }
  }

  // -- Bulk assign to group -----------------------------------------------------
  // Shares StudentAssignDialog with the Users page; it owns group fetching and the
  // confirm POST itself, so this composable only owns which rows it's open with.
  const assignOpen = ref(false)
  const assignStudents = ref<AdminUser[]>([])

  const openBatchAssign = (): void => {
    if (!canAssignToGroup.value) return
    assignStudents.value = Array.from(selectedMap.value.values())
    assignOpen.value = true
  }

  const onAssignConfirmed = (): void => {
    clearSelection()
    reload()
  }

  // -- Lookups for the edit form sheet (countries / states / supervisors) --------
  const countries = ref<AdminUserCountry[]>([])
  const states = ref<AdminUserState[]>([])
  const supervisors = ref<AdminUser[]>([])

  const init = async (): Promise<void> => {
    try {
      const [allCountries, allStates] = await Promise.all([fetchAdminCountries(), fetchAdminStates()])
      countries.value = allCountries
      states.value = allStates
    } catch (metaError) {
      logApiError('admin.views.meta', metaError)
    }
    try {
      const data = await fetchAdminUsers({ page: 1, limit: 200, role: 'supervisor' })
      supervisors.value = data.items
    } catch (supError) {
      logApiError('admin.views.supervisors', supError)
    }
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
    busy,
    loadResults,
    reload,
    onSortChange,
    onPageChange,
    onPageSizeChange,
    onGroupByChange,
    selectedIds,
    bulkCount,
    canAssignToGroup,
    clearSelection,
    onSelectedChange,
    viewOpen,
    detailUser,
    openView,
    onViewClose,
    onRowClick,
    singleToggle,
    onToggleActive,
    runSingleToggle,
    singleDelete,
    singleDeleteConfirmText,
    singleDeleteConfirmBlocked,
    runSingleDelete,
    bulkStatus,
    confirmBulkStatus,
    runBulkStatus,
    bulkDelete,
    bulkForce,
    deleteConfirmText,
    bulkDeleteMessage,
    deleteConfirmBlocked,
    confirmBulkDelete,
    runBulkDelete,
    assignOpen,
    assignStudents,
    openBatchAssign,
    onAssignConfirmed,
    countries,
    states,
    supervisors,
    init
  }
}
