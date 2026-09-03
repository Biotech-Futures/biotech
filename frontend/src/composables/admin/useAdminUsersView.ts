import { computed, ref, watch, type Ref } from 'vue'
import { type AdminColumn, type SortState } from '@/components/admin/AdminDataTable.vue'
import {
  type AdminUser,
  type AdminUserCountry,
  type AdminUserState,
  type UserListFilters,
  fetchAdminUsers,
  deleteAdminUser,
  setAdminUserActive,
  bulkSetUsersActive,
  bulkDeleteUsers,
  fetchAdminCountries,
  fetchAdminStates,
  removeGroupMember
} from '@/utils/adminAPI'
import { logApiError } from '@/utils/apiError'
import { defaultAdminUserFilters, type AdminUserFilters } from '@/utils/userOptions'
import { userName } from '@/utils/userFormat'

interface UseAdminUsersViewOptions {
  /** Resolved role filter for single-role tabs (students / mentors / supervisors). */
  roleFilter: Ref<string>
  /** Human noun for this tab (user / student / supervisor). */
  noun: Ref<string>
}

/**
 * State and behaviour for the admin users list: server-side data fetching,
 * filters, search, sorting, pagination, row/bulk selection, and the single /
 * bulk status, delete and student-group actions.
 */
export function useAdminUsersView({ roleFilter, noun }: UseAdminUsersViewOptions) {
  // -- Tab mode --------------------------------------------------------------
  const fixedRole = computed(() => roleFilter.value || '')
  // Any role-fixed tab (students / mentors / supervisors) locks the role.
  const isRoleFixed = computed(() => Boolean(roleFilter.value))
  // Supervisors alone use the compact top-bar layout and are locked down
  // (no bulk delete, no delete from the editor).
  const isSupervisorMode = computed(() => roleFilter.value === 'supervisor')
  // Students get the group-assignment mode: Group column, Assign/Remove actions,
  // an "In group" filter, and batch assign/remove.
  const isStudentMode = computed(() => roleFilter.value === 'student')
  const userNoun = computed(() => noun.value)
  const pluralNoun = computed(() => noun.value + 's')
  const addLabel = computed(() => `Add ${noun.value.charAt(0).toUpperCase() + noun.value.slice(1)}`)

  // -- Loading state ---------------------------------------------------------
  const loading = ref(false)
  const busy = ref(false)
  const error = ref('')

  const rows = ref<AdminUser[]>([])
  const totalCount = ref(0)
  const page = ref(1)
  const limit = ref(25)
  const sortState = ref<SortState>({
    key: isStudentMode.value ? 'student' : roleFilter.value ? 'name' : 'createdAt',
    direction: roleFilter.value ? 'asc' : 'desc'
  })

  const countries = ref<AdminUserCountry[]>([])
  const filterCountries = ref<AdminUserCountry[]>([])
  const states = ref<AdminUserState[]>([])
  const supervisors = ref<AdminUser[]>([])

  // -- Search (debounced) ----------------------------------------------------
  const searchInput = ref('')
  let searchTimer: ReturnType<typeof setTimeout> | null = null
  const appliedSearch = ref('')

  watch(searchInput, (value) => {
    if (searchTimer) clearTimeout(searchTimer)
    searchTimer = setTimeout(() => {
      appliedSearch.value = value.trim()
      clearSelection()
      reload()
    }, 350)
  })

  // -- Filters ---------------------------------------------------------------
  const filters = ref<AdminUserFilters>(defaultAdminUserFilters())

  // Filters shared by the list query and "select all matching" bulk actions.
  const currentFilters = computed<UserListFilters>(() => ({
    search: appliedSearch.value || undefined,
    role: fixedRole.value || (filters.value.role === 'all' ? undefined : filters.value.role),
    country: filters.value.country === 'all' ? undefined : filters.value.country,
    state: filters.value.state === 'all' ? undefined : filters.value.state,
    active: filters.value.status === 'all' ? undefined : filters.value.status,
    inGroup: isStudentMode.value && filters.value.inGroup !== 'all' ? filters.value.inGroup : undefined
  }))

  // Bulk endpoints expect `active` as a boolean, not the list-query string.
  const bulkFilters = computed<UserListFilters>(() => ({
    ...currentFilters.value,
    active: filters.value.status === 'all' ? undefined : filters.value.status === 'active'
  }))

  const hasActiveFilters = computed(
    () =>
      Boolean(
        filters.value.role !== 'all' ||
          filters.value.country !== 'all' ||
          filters.value.state !== 'all' ||
          filters.value.status !== 'all' ||
          (isStudentMode.value && filters.value.inGroup !== 'all') ||
          appliedSearch.value
      )
  )

  // -- Data loading ----------------------------------------------------------
  const sortByFromKey: Record<string, string> = {
    name: 'name',
    email: 'email',
    student: 'name'
  }

  const load = async () => {
    loading.value = true
    error.value = ''
    try {
      const data = await fetchAdminUsers({
        page: page.value,
        limit: limit.value,
        search: appliedSearch.value || undefined,
        role: currentFilters.value.role,
        state: currentFilters.value.state,
        country: currentFilters.value.country,
        active:
          filters.value.status === 'all'
            ? undefined
            : filters.value.status === 'active',
        inGroup: currentFilters.value.inGroup,
        sortBy: sortByFromKey[sortState.value.key] || 'createdAt',
        sortOrder: sortState.value.direction
      })
      rows.value = data.items
      totalCount.value = data.total
    } catch (loadError) {
      logApiError('admin.users.list', loadError)
      error.value =
        loadError instanceof Error ? loadError.message : `${pluralNoun.value} could not be loaded right now.`
      rows.value = []
      totalCount.value = 0
    } finally {
      loading.value = false
    }
  }

  const reload = () => {
    page.value = 1
    void load()
  }

  // -- Selection -------------------------------------------------------------
  // Keep a snapshot of each selected row so group-actions (assign / remove)
  // can read group info for selections that span pages; the table only emits
  // ids, so snapshots are rebuilt from that set and refreshed on refetch.
  const selectedMap = ref<Map<number, AdminUser>>(new Map())
  const selectAllMatching = ref(false)
  const excludedIds = ref<Set<string>>(new Set())

  const selectedIds = computed(() => Array.from(selectedMap.value.keys()))

  const pageIds = computed(() => rows.value.map((row) => String(row.id)))
  const pageRows = computed(() => rows.value.length)

  const displaySelected = computed<Array<string | number>>(() => {
    if (selectAllMatching.value) {
      return pageIds.value.filter((id) => !excludedIds.value.has(id))
    }
    return selectedIds.value
  })

  const excludedCount = computed(() => excludedIds.value.size)
  const effectiveSelectAllCount = computed(() => Math.max(0, totalCount.value - excludedCount.value))
  const bulkCount = computed(() =>
    selectAllMatching.value ? effectiveSelectAllCount.value : selectedMap.value.size
  )

  // The students really in a group, from the selected snapshots.
  const groupedSelected = computed(() =>
    Array.from(selectedMap.value.values()).filter((user) => Boolean(user.groupId))
  )
  const groupedCount = computed(() => groupedSelected.value.length)

  const allOnPageSelected = computed(() => {
    const shown = new Set(displaySelected.value.map((id) => String(id)))
    return pageIds.value.length > 0 && pageIds.value.every((id) => shown.has(id))
  })

  const selectionBanner = computed(
    () => selectAllMatching.value || (allOnPageSelected.value && totalCount.value > pageRows.value)
  )

  // Filters / search / sort redefine the matching set, so drop the selection.
  const clearSelection = () => {
    selectedMap.value = new Map()
    selectAllMatching.value = false
    excludedIds.value = new Set()
  }

  const onSelectedChange = (value: Array<string | number>) => {
    if (selectAllMatching.value) {
      const next = new Set(excludedIds.value)
      pageIds.value.forEach((id) => {
        if (value.includes(id)) next.delete(id)
        else next.add(id)
      })
      excludedIds.value = next
      return
    }
    // Rebuild the snapshots, keeping any we already had so off-page selections
    // retain their group info for the remove/assign bulk actions.
    const rowById = new Map(rows.value.map((row) => [row.id, row]))
    const next = new Map<number, AdminUser>()
    for (const id of value) {
      const numericId = Number(id)
      const existing = selectedMap.value.get(numericId)
      next.set(
        numericId,
        existing ?? rowById.get(numericId) ?? ({ id: numericId } as AdminUser)
      )
    }
    selectedMap.value = next
  }

  // Refresh snapshots for rows that just reloaded, so group changes made
  // elsewhere (assignments, removals) are reflected in the bulk-action counts.
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

  const selectAllMatchingNow = () => {
    selectedMap.value = new Map()
    excludedIds.value = new Set()
    selectAllMatching.value = true
  }

  // -- Reactive filter patching (from the filter card) -----------------------
  const applyFilterPatch = ({ field, value }: { field: string; value: string }) => {
    filters.value = { ...filters.value, [field]: value }
    if (field === 'country') filters.value.state = 'all'
    clearSelection()
    reload()
  }

  // -- Pagination / sorting --------------------------------------------------
  const onSortChange = (next: SortState) => {
    sortState.value = next
    clearSelection()
    reload()
  }

  const onPageChange = (next: number) => {
    page.value = next
    void load()
  }

  const onPageSizeChange = (size: number) => {
    limit.value = size
    page.value = 1
    void load()
  }

  // -- Columns ---------------------------------------------------------------
  // Columns (name/email sortable, matching the portal). Single-role tabs
  // (students / mentors) drop the redundant Role column; users & supervisors keep it.
  // Students get their own layout: a single Student column (name with email
  // subtext, like the mentors tab) plus School / Year / Interests and a Group
  // column for the assignment features.
  const columns = computed<AdminColumn[]>(() => {
    const base: AdminColumn[] = [
      { key: 'name', label: 'Name', sortable: true },
      { key: 'email', label: 'Email', sortable: true },
      { key: 'country', label: 'Country' },
      { key: 'state', label: 'State' },
      { key: 'status', label: 'Status' },
      { key: 'loggedIn', label: 'Logged In' },
      { key: 'actions', label: 'Actions', align: 'right' }
    ]
    if (isRoleFixed.value && !isSupervisorMode.value) {
      if (isStudentMode.value) {
        return [
          { key: 'student', label: 'Student', sortable: true },
          { key: 'school', label: 'School' },
          { key: 'year', label: 'Year' },
          { key: 'country', label: 'Country' },
          { key: 'state', label: 'State' },
          { key: 'group', label: 'Group' },
          { key: 'interests', label: 'Interests' },
          { key: 'loggedIn', label: 'Logged In' },
          { key: 'actions', label: 'Actions', align: 'right' }
        ]
      }
      return base
    }
    return [base[0], base[1], { key: 'role', label: 'Role' }, ...base.slice(2)]
  })

  const emptyMessage = computed(() =>
    loading.value
      ? ''
      : `No ${pluralNoun.value} found${hasActiveFilters.value ? ' for the current filters.' : '.'}`
  )

  // -- Detail sheet ----------------------------------------------------------
  const viewOpen = ref(false)
  const detailUser = ref<AdminUser | null>(null)

  const detailTitle = computed(() => {
    const name = [detailUser.value?.firstName, detailUser.value?.lastName]
      .filter(Boolean)
      .join(' ')
      .trim()
    return name || 'User details'
  })

  const openView = (user: AdminUser) => {
    detailUser.value = user
    viewOpen.value = true
  }

  const onViewClose = () => {
    viewOpen.value = false
    detailUser.value = null
  }

  // Row click opens the detail sheet.
  const onRowClick = (row: Record<string, unknown>) => {
    openView(row as unknown as AdminUser)
  }

  // -- Single status toggle --------------------------------------------------
  const singleToggle = ref({ open: false, userId: 0, message: '' })

  const onToggleActive = (user: AdminUser) => {
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

  const runActiveChange = async (userId: number, isActive: boolean): Promise<boolean> => {
    busy.value = true
    try {
      await setAdminUserActive(userId, isActive)
      void load()
      return true
    } catch (toggleError) {
      logApiError('admin.users.toggle', toggleError)
      return false
    } finally {
      busy.value = false
    }
  }

  const runSingleToggle = async () => {
    if (!singleToggle.value.userId) return
    const ok = await runActiveChange(singleToggle.value.userId, false)
    if (ok) singleToggle.value = { open: false, userId: 0, message: '' }
  }

  // -- Single delete ---------------------------------------------------------
  const singleDelete = ref<{
    open: boolean
    userId: number
    message: string
    force: boolean
  }>({ open: false, userId: 0, message: '', force: false })

  const singleDeleteConfirmBlocked = computed(
    () => singleDelete.value.force && singleDeleteConfirmText.value !== 'DELETE'
  )
  const singleDeleteConfirmText = ref('')

  const runSingleDelete = async () => {
    const userId = singleDelete.value.userId
    if (!userId) return
    busy.value = true
    try {
      await deleteAdminUser(userId, singleDelete.value.force)
      singleDelete.value = { open: false, userId: 0, message: '', force: false }
      singleDeleteConfirmText.value = ''
      viewOpen.value = false
      detailUser.value = null
      clearSelection()
      void load()
    } catch (deleteError) {
      logApiError('admin.users.delete', deleteError)
      error.value =
        deleteError instanceof Error
          ? deleteError.message
          : 'Unable to delete the user right now.'
    } finally {
      busy.value = false
    }
  }

  // -- Bulk status -----------------------------------------------------------
  const bulkStatus = ref<{
    open: boolean
    action: 'activate' | 'deactivate'
    title: string
    message: string
    confirmLabel: string
  }>({ open: false, action: 'activate', title: '', message: '', confirmLabel: '' })

  const confirmBulkStatus = (isActive: boolean) => {
    const action = isActive ? 'activate' : 'deactivate'
    bulkStatus.value = {
      open: true,
      action,
      confirmLabel: isActive ? 'Activate' : 'Deactivate',
      title: `${isActive ? 'Activate' : 'Deactivate'} ${bulkCount.value} ${pluralNoun.value}?`,
      message: isActive
        ? 'The selected users will be able to sign in again.'
        : 'The selected users will no longer be able to sign in. You can reactivate them at any time.'
    }
  }

  const runBulkStatus = async () => {
    busy.value = true
    try {
      const isActive = bulkStatus.value.action === 'activate'
      if (selectAllMatching.value) {
        await bulkSetUsersActive({
          isActive,
          selectAll: true,
          filters: bulkFilters.value,
          excludeIds: [...excludedIds.value].map(Number),
          userIds: []
        })
      } else {
        await bulkSetUsersActive({
          isActive,
          userIds: selectedIds.value
        })
      }
      bulkStatus.value = { ...bulkStatus.value, open: false }
      clearSelection()
      void load()
    } catch (bulkError) {
      logApiError('admin.users.bulk-status', bulkError)
    } finally {
      busy.value = false
    }
  }

  // -- Bulk delete -----------------------------------------------------------
  const bulkDelete = ref({ open: false })
  const bulkForce = ref(false)
  const deleteConfirmText = ref('')

  const bulkDeleteMessage = computed(() => {
    const count = bulkCount.value
    const base = `This permanently removes the selected ${count === 1 ? 'account' : 'accounts'} and all related data. This cannot be undone.`
    if (selectAllMatching.value) {
      return `${base} Every account matching the current filters will be deleted; admin accounts are protected and skipped.`
    }
    return base
  })

  const deleteConfirmBlocked = computed(
    () => (selectAllMatching.value || bulkForce.value) && deleteConfirmText.value !== 'DELETE'
  )

  const confirmBulkDelete = () => {
    bulkForce.value = false
    deleteConfirmText.value = ''
    bulkDelete.value = { open: true }
  }

  const runBulkDelete = async () => {
    busy.value = true
    try {
      let result
      if (selectAllMatching.value) {
        result = await bulkDeleteUsers({
          userIds: [],
          force: bulkForce.value,
          selectAll: true,
          filters: bulkFilters.value,
          excludeIds: [...excludedIds.value].map(Number),
          expectedCount: bulkCount.value
        })
      } else {
        result = await bulkDeleteUsers({
          userIds: selectedIds.value,
          force: bulkForce.value
        })
      }
      bulkDelete.value = { open: false }
      clearSelection()
      void load()
      if (result?.msg) {
        error.value = result.msg
      }
    } catch (bulkError) {
      logApiError('admin.users.bulk-delete', bulkError)
      error.value =
        bulkError instanceof Error
          ? bulkError.message
          : 'Unable to delete the selected users right now.'
    } finally {
      busy.value = false
    }
  }

  // -- Student group actions -------------------------------------------------
  // Single and batch assignment share one surface; the student assign dialog
  // owns group fetching, capacity, and the confirm POST.
  const assignOpen = ref(false)
  const assignStudents = ref<AdminUser[]>([])

  const openAssign = (user: AdminUser) => {
    assignStudents.value = [user]
    assignOpen.value = true
  }

  const openBatchAssign = () => {
    assignStudents.value = Array.from(selectedMap.value.values())
    assignOpen.value = true
  }

  const onAssignConfirmed = () => {
    clearSelection()
    reload()
  }

  const singleRemove = ref<{ open: boolean; user: AdminUser | null; message: string }>({
    open: false,
    user: null,
    message: ''
  })

  const onGroupAction = (user: AdminUser) => {
    if (user.groupId) {
      singleRemove.value = {
        open: true,
        user,
        message: `Remove ${userName(user)} from ${user.groupName || 'their group'}? They will become ungrouped and can be reassigned at any time.`
      }
      return
    }
    openAssign(user)
  }

  const runSingleRemove = async () => {
    const user = singleRemove.value.user
    if (!user || !user.groupId) return
    busy.value = true
    let failure = ''
    try {
      await removeGroupMember(user.groupId, user.id)
      singleRemove.value = { open: false, user: null, message: '' }
    } catch (removeError) {
      logApiError('admin.students.remove', removeError)
      failure =
        removeError instanceof Error
          ? removeError.message
          : 'Unable to remove the student from their group.'
    } finally {
      busy.value = false
    }
    void load().then(() => {
      if (failure) error.value = failure
    })
  }

  const batchRemoveConfirm = ref({ open: false })

  const batchRemoveTitle = computed(() => {
    const count = groupedCount.value
    return `Remove ${count} ${count === 1 ? 'student' : 'students'} from ${count === 1 ? 'their group' : 'their groups'}?`
  })

  const batchRemoveMessage = 'They will become ungrouped and can be reassigned at any time.'

  const openBatchRemove = () => {
    batchRemoveConfirm.value = { open: true }
  }

  const runBatchRemove = async () => {
    const targets = groupedSelected.value
    if (!targets.length) {
      batchRemoveConfirm.value = { open: false }
      return
    }
    busy.value = true
    let removedCount = 0
    let failedCount = 0
    const removedIds = new Set<number>()
    try {
      // Settle every removal independently so one failure doesn't strand the rest.
      const outcomes = await Promise.allSettled(
        targets.map((user) => removeGroupMember(user.groupId!, user.id))
      )
      outcomes.forEach((outcome, index) => {
        if (outcome.status === 'fulfilled') {
          removedCount += 1
          removedIds.add(targets[index].id)
        } else {
          failedCount += 1
          logApiError('admin.students.batch-remove', outcome.reason)
        }
      })
      if (removedCount) {
        // Drop only the students we actually removed; keep other selections.
        const next = new Map(selectedMap.value)
        removedIds.forEach((id) => next.delete(id))
        selectedMap.value = next
      }
      batchRemoveConfirm.value = { open: false }
    } finally {
      busy.value = false
    }
    const failure =
      failedCount > 0
        ? `Removed ${removedCount}, but ${failedCount} could not be removed.`
        : ''
    void load().then(() => {
      if (failure) error.value = failure
    })
  }

  // Bulk-bar title hints for the group actions (disabled state explanation first).
  const groupActionsHint = computed(() =>
    selectAllMatching.value
      ? 'Select students individually to assign or remove from groups'
      : undefined
  )

  const removeGroupActionsHint = computed(() => {
    if (selectAllMatching.value) return groupActionsHint.value
    if (groupedCount.value === 0) return 'None of the selected students are in a group'
    return undefined
  })

  // -- Initial load ------------------------------------------------------------
  const init = async () => {
    void load()
    try {
      const [allCountries, inUseCountries, allStates] = await Promise.all([
        fetchAdminCountries(),
        fetchAdminCountries({ inUse: true }),
        fetchAdminStates()
      ])
      countries.value = allCountries
      filterCountries.value = inUseCountries
      states.value = allStates
    } catch (metaError) {
      logApiError('admin.users.meta', metaError)
    }
    if (!isSupervisorMode.value) {
      try {
        const data = await fetchAdminUsers({ page: 1, limit: 200, role: 'supervisor' })
        supervisors.value = data.items
      } catch (supError) {
        logApiError('admin.users.supervisors', supError)
      }
    }
  }

  watch(roleFilter, () => {
    filters.value = defaultAdminUserFilters()
    clearSelection()
    reload()
  })

  return {
    loading,
    busy,
    error,
    rows,
    totalCount,
    page,
    limit,
    sortState,
    countries,
    filterCountries,
    states,
    supervisors,
    searchInput,
    filters,
    currentFilters,
    hasActiveFilters,
    columns,
    emptyMessage,
    selectedMap,
    selectAllMatching,
    excludedIds,
    displaySelected,
    excludedCount,
    effectiveSelectAllCount,
    bulkCount,
    groupedSelected,
    groupedCount,
    selectionBanner,
    pageRows,
    singleToggle,
    bulkStatus,
    bulkDelete,
    bulkForce,
    deleteConfirmText,
    bulkDeleteMessage,
    deleteConfirmBlocked,
    assignOpen,
    assignStudents,
    singleRemove,
    batchRemoveConfirm,
    batchRemoveTitle,
    batchRemoveMessage,
    groupActionsHint,
    removeGroupActionsHint,
    viewOpen,
    detailUser,
    detailTitle,
    isStudentMode,
    isSupervisorMode,
    isRoleFixed,
    fixedRole,
    userNoun,
    pluralNoun,
    addLabel,
    applyFilterPatch,
    onSortChange,
    onPageChange,
    onPageSizeChange,
    onSelectedChange,
    clearSelection,
    selectAllMatchingNow,
    onRowClick,
    openView,
    onViewClose,
    onToggleActive,
    runSingleToggle,
    singleDelete,
    singleDeleteConfirmText,
    singleDeleteConfirmBlocked,
    runSingleDelete,
    confirmBulkStatus,
    runBulkStatus,
    confirmBulkDelete,
    runBulkDelete,
    openAssign,
    openBatchAssign,
    onAssignConfirmed,
    onGroupAction,
    runSingleRemove,
    runBatchRemove,
    openBatchRemove,
    init,
    load,
    reload
  }
}