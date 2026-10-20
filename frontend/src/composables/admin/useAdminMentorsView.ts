import { computed, reactive, ref } from 'vue'
import {
  type AdminMentorDetail,
  type MatchedGroup,
  type MentorListItem,
  bulkSetUsersActive,
  fetchAdminMentorDetails,
  fetchMatchedGroups,
  fetchMentorMatchMentorList,
  setAdminMentorActive
} from '@/utils/adminAPI'
import { logApiError } from '@/utils/apiError'
import { mentorConcern } from '@/utils/mentorFormat'
import { useIdleThreshold } from '@/composables/admin/useIdleThreshold'

export type MentorSortKey =
  | 'name'
  | 'country'
  | 'institution'
  | 'capacity'
  | 'lastMessage'
  | 'status'
  | 'loggedIn'
export type MentorSortDirection = 'asc' | 'desc'

export interface MentorBulkAction {
  open: boolean
  action: 'activate' | 'deactivate'
  count: number
}

/**
 * State and behaviour for the admin mentors list: client-side sorting (matching
 * the portal), expandable rows, row/bulk selection, active-status toggling, the
 * inactive-threshold control, and the replace-inactive-mentors flow.
 */
export function useAdminMentorsView() {
  const loading = ref(true)
  const statusBusy = ref(false)
  const error = ref('')

  const mentors = ref<AdminMentorDetail[]>([])
  const matchedGroups = ref<MatchedGroup[]>([])
  const mentorList = ref<MentorListItem[]>([])

  // Shared with Matched Groups, so both screens count idle mentors the
  // same way. Exposed under its existing name for the view.
  const { idleDays: inactiveDays, setIdleDays } = useIdleThreshold()
  const selectedIds = ref<Set<number>>(new Set())
  const bulkAction = reactive<MentorBulkAction>({
    open: false,
    action: 'activate',
    count: 0
  })
  const replaceDialogOpen = ref(false)

  const sortState = ref<{ key: MentorSortKey; direction: MentorSortDirection }>({
    key: 'name',
    direction: 'asc'
  })

  // Groups needing a new mentor, for either reason: the account is deactivated,
  // or the mentor has gone quiet. Reads the unfiltered list on purpose, so a
  // deactivated mentor's group is still offered even though the table hides them.
  const inactiveGroups = computed(() => {
    const needsReplacing = new Set(
      mentors.value
        .filter((mentor) => mentorConcern(mentor, inactiveDays.value) !== null)
        .map((mentor) => mentor.mentorId)
    )
    return matchedGroups.value.filter((group) => needsReplacing.has(group.mentor.mentorId))
  })

  // -- Data loading -----------------------------------------------------------

  const load = async () => {
    loading.value = true
    error.value = ''
    try {
      const [detailData, matchedData] = await Promise.all([
        fetchAdminMentorDetails(),
        fetchMatchedGroups()
      ])
      mentors.value = detailData
      matchedGroups.value = matchedData
      void loadMentorPool()
    } catch (loadError) {
      logApiError('admin.mentors.load', loadError)
      error.value = loadError instanceof Error ? loadError.message : 'Unable to load mentors.'
      mentors.value = []
      matchedGroups.value = []
      mentorList.value = []
    } finally {
      loading.value = false
    }
  }

  // The replacement pool is only needed when the replace dialog opens; don't fail
  // the whole tab if it's unavailable.
  const loadMentorPool = async () => {
    try {
      mentorList.value = await fetchMentorMatchMentorList()
    } catch (poolError) {
      logApiError('admin.mentors.list', poolError)
      mentorList.value = []
    }
  }

  // -- Sorting (client-side, matches adminweb) --------------------------------

  const getSortValue = (mentor: AdminMentorDetail, key: MentorSortKey): string | number => {
    switch (key) {
      case 'name':
        return `${mentor.name} ${mentor.email ?? ''}`
      case 'country':
        return mentor.countryName ?? ''
      case 'institution':
        return mentor.institution ?? ''
      case 'capacity':
        return mentor.remainingCapacity
      case 'lastMessage':
        return mentor.lastMessageAt ?? ''
      case 'status':
        return mentor.isActive ? 'Active' : 'Inactive'
      case 'loggedIn':
        return mentor.hasLoggedIn ? mentor.lastLogin ?? '' : ''
    }
  }

  const sortedMentors = computed(() => {
    const direction = sortState.value.direction === 'asc' ? 1 : -1
    const comparators: Record<MentorSortKey, (a: AdminMentorDetail, b: AdminMentorDetail) => number> = {
      name: (a, b) => `${a.name} ${a.email ?? ''}`.localeCompare(`${b.name} ${b.email ?? ''}`),
      country: (a, b) => (a.countryName ?? '').localeCompare(b.countryName ?? ''),
      institution: (a, b) => (a.institution ?? '').localeCompare(b.institution ?? ''),
      capacity: (a, b) => a.remainingCapacity - b.remainingCapacity,
      lastMessage: (a, b) =>
        getSortValue(a, 'lastMessage').toString().localeCompare(getSortValue(b, 'lastMessage').toString()),
      status: (a, b) => Number(a.isActive) - Number(b.isActive),
      loggedIn: (a, b) => {
        const hasLoggedInCompare = Number(Boolean(a.hasLoggedIn)) - Number(Boolean(b.hasLoggedIn))
        if (hasLoggedInCompare !== 0) return hasLoggedInCompare
        return (a.lastLogin ?? '').localeCompare(b.lastLogin ?? '')
      }
    }
    // Only active accounts are listed: a deactivated mentor is managed from the
    // Users page. Their groups still surface under "Replace Inactive Mentors",
    // which reads the unfiltered list below.
    const visible = mentors.value.filter((mentor) => mentor.isActive)
    return [...visible].sort((a, b) => comparators[sortState.value.key](a, b) * direction)
  })

  const setSort = (key: MentorSortKey) => {
    if (sortState.value.key !== key) {
      sortState.value = { key, direction: 'asc' }
    } else {
      sortState.value = {
        key,
        direction: sortState.value.direction === 'asc' ? 'desc' : 'asc'
      }
    }
  }

  // -- Selection -------------------------------------------------------------

  const clearSelection = () => {
    selectedIds.value = new Set()
  }

  // -- Status -----------------------------------------------------------------

  const onInactiveDaysChange = (event: Event) => {
    setIdleDays(Number((event.target as HTMLInputElement).value))
  }

  const toggleActive = async (mentor: AdminMentorDetail) => {
    statusBusy.value = true
    error.value = ''
    try {
      await setAdminMentorActive(mentor.mentorId, !mentor.isActive)
      await load()
    } catch (toggleError) {
      logApiError('admin.mentors.toggle', toggleError)
      error.value =
        toggleError instanceof Error
          ? toggleError.message
          : 'Unable to update the mentor status.'
    } finally {
      statusBusy.value = false
    }
  }

  const openBulk = (action: 'activate' | 'deactivate') => {
    bulkAction.action = action
    bulkAction.count = selectedIds.value.size
    bulkAction.open = true
  }

  const bulkTitle = computed(() => {
    const count = bulkAction.count
    return `${bulkAction.action === 'activate' ? 'Activate' : 'Deactivate'} ${count} ${count === 1 ? 'mentor' : 'mentors'}?`
  })

  const bulkMessage = computed(() =>
    bulkAction.action === 'activate'
      ? 'The selected mentors will be able to sign in again.'
      : 'The selected mentors will no longer be able to sign in. You can reactivate them at any time.'
  )

  const runBulkStatus = async () => {
    if (statusBusy.value) return
    const ids = Array.from(selectedIds.value)
    if (ids.length === 0) {
      bulkAction.open = false
      return
    }
    statusBusy.value = true
    error.value = ''
    try {
      await bulkSetUsersActive({
        userIds: ids,
        isActive: bulkAction.action === 'activate'
      })
      bulkAction.open = false
      selectedIds.value = new Set()
      await load()
    } catch (bulkError) {
      logApiError('admin.mentors.bulk-status', bulkError)
      error.value =
        bulkError instanceof Error
          ? bulkError.message
          : 'Unable to update mentor statuses right now.'
    } finally {
      statusBusy.value = false
    }
  }

  // -- Replace inactive mentors -----------------------------------------------

  const onReplaceConfirmed = () => {
    void load()
  }

  return {
    loading,
    statusBusy,
    error,
    mentors,
    matchedGroups,
    mentorList,
    inactiveDays,
    selectedIds,
    bulkAction,
    replaceDialogOpen,
    sortState,
    inactiveGroups,
    sortedMentors,
    setSort,
    clearSelection,
    onInactiveDaysChange,
    toggleActive,
    openBulk,
    bulkTitle,
    bulkMessage,
    runBulkStatus,
    onReplaceConfirmed,
    load
  }
}
