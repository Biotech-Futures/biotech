<template>
  <div class="content-area admin-views">
    <div class="page-header">
      <h1 class="page-title">Views</h1>
      <p class="page-subtitle">
        Create and manage saved user segments, cohorts and mini-reports.
      </p>
    </div>

    <div class="admin-views__main">
      <div class="admin-views__toolbar">
        <div class="tab-bar" role="tablist" aria-label="View categories">
          <button
            v-for="tab in TABS"
            :key="tab.key"
            type="button"
            role="tab"
            class="tab-pill"
            :class="{ active: activeTab === tab.key }"
            :aria-selected="activeTab === tab.key"
            @click="activeTab = tab.key"
          >
            {{ tab.label }} ({{ tabCounts[tab.key] }})
          </button>
        </div>

        <button type="button" class="btn btn-primary" @click="openCreate">
          <i class="fas fa-plus" aria-hidden="true"></i>
          <span>Create View</span>
        </button>
      </div>

      <p v-if="error" class="admin-views__error" role="alert">
        <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
        <span>{{ error }}</span>
      </p>

      <BulkActionsBar
        v-if="selectedIds.length"
        :count="selectedIds.length"
        noun="view"
        :disabled="bulkActionBusy"
        @clear="clearSelection"
      >
        <button type="button" class="btn btn-sm btn-outline" :disabled="bulkActionBusy" @click="batchExport">
          Batch export
        </button>
        <button type="button" class="btn btn-sm btn-danger" :disabled="bulkActionBusy" @click="openBulkDelete">
          Batch delete
        </button>
      </BulkActionsBar>

      <AdminViewsDirectoryTable
        :views="filteredViews"
        :loading="loading"
        v-model:selected="selectedIds"
        v-model:search="searchInput"
        @edit="openEdit"
        @changed="load"
      >
        <!-- Type and target role, beside Search. -->
        <template #filters>
          <div class="table-filter-field">
            <label class="table-filter-label" for="view-type-filter">Type</label>
            <AppSelect id="view-type-filter" v-model="activeTab" class="table-filter" :options="TYPE_OPTIONS" />
          </div>

          <div class="table-filter-field">
            <label class="table-filter-label" for="view-role-filter">Target role</label>
            <AppSelect id="view-role-filter" v-model="roleFilter" class="table-filter" :options="ROLE_OPTIONS" />
          </div>
        </template>
      </AdminViewsDirectoryTable>
    </div>

    <AdminViewQueryDrawer v-model="drawerOpen" :view="editingView" @saved="onSaved" />

    <ConfirmDialog
      v-model="bulkDeleteConfirmOpen"
      title="Delete selected views"
      :message="bulkDeleteMessage"
      confirm-label="Delete"
      variant="danger"
      :busy="bulkActionBusy"
      @confirm="confirmBulkDelete"
      @cancel="bulkDeleteConfirmOpen = false"
    >
      <p v-if="bulkDeleteError" class="admin-views__dialog-error" role="alert">{{ bulkDeleteError }}</p>
    </ConfirmDialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import AppSelect, { type AppSelectOption } from '@/components/AppSelect.vue'
import BulkActionsBar from '@/components/admin/BulkActionsBar.vue'
import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import AdminViewQueryDrawer from '@/components/admin/views/AdminViewQueryDrawer.vue'
import AdminViewsDirectoryTable from '@/components/admin/views/AdminViewsDirectoryTable.vue'
import { bulkDeleteAdminViews, fetchAdminViews, getAdminViewExportUrl, type AdminView } from '@/utils/adminAPI'
import { logApiError } from '@/utils/apiError'
import { roleLabel } from '@/utils/userFormat'
import { USER_ROLES } from '@/utils/userOptions'

const TYPE_OPTIONS: AppSelectOption[] = [
  { value: 'all', label: 'All types' },
  { value: 'default', label: 'Default' },
  { value: 'custom', label: 'Custom' }
]

const ROLE_OPTIONS: AppSelectOption[] = [
  { value: 'all', label: 'All roles' },
  ...USER_ROLES.map((role) => ({ value: role, label: roleLabel(role) }))
]

type TabKey = 'all' | 'default' | 'custom'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'all', label: 'All Views' },
  { key: 'default', label: 'Default Views' },
  { key: 'custom', label: 'Custom Views' }
]

const views = ref<AdminView[]>([])
const loading = ref(false)
const error = ref('')
const searchInput = ref('')
const roleFilter = ref('all')
const activeTab = ref<TabKey>('all')
const drawerOpen = ref(false)
const editingView = ref<AdminView | null>(null)
const selectedIds = ref<Array<string | number>>([])
const bulkDeleteConfirmOpen = ref(false)
const bulkActionBusy = ref(false)
const bulkDeleteError = ref('')

const router = useRouter()

let searchDebounce: ReturnType<typeof setTimeout> | undefined

const load = async () => {
  loading.value = true
  error.value = ''
  selectedIds.value = []
  try {
    const data = await fetchAdminViews({
      role: roleFilter.value === 'all' ? undefined : roleFilter.value,
      search: searchInput.value || undefined
    })
    views.value = data.items
  } catch (loadError) {
    logApiError('admin.views.list', loadError)
    error.value = loadError instanceof Error ? loadError.message : 'Views could not be loaded right now.'
    views.value = []
  } finally {
    loading.value = false
  }
}

const tabCounts = computed(() => {
  const defaultCount = views.value.filter((view) => view.isDefault).length
  return {
    all: views.value.length,
    default: defaultCount,
    custom: views.value.length - defaultCount
  }
})

const filteredViews = computed(() => {
  if (activeTab.value === 'default') return views.value.filter((view) => view.isDefault)
  if (activeTab.value === 'custom') return views.value.filter((view) => !view.isDefault)
  return views.value
})

const openCreate = () => {
  editingView.value = null
  drawerOpen.value = true
}

const openEdit = (view: AdminView) => {
  editingView.value = view
  drawerOpen.value = true
}

const bulkDeleteMessage = computed(() =>
  `Delete ${selectedIds.value.length} selected view${selectedIds.value.length === 1 ? '' : 's'}? This cannot be undone.`
)

const clearSelection = () => {
  selectedIds.value = []
}

const batchExport = () => {
  selectedIds.value.forEach((id) => {
    window.open(getAdminViewExportUrl(Number(id)), '_blank')
  })
}

const openBulkDelete = () => {
  bulkDeleteError.value = ''
  bulkDeleteConfirmOpen.value = true
}

const confirmBulkDelete = async () => {
  if (bulkActionBusy.value) return
  bulkActionBusy.value = true
  bulkDeleteError.value = ''
  try {
    await bulkDeleteAdminViews(selectedIds.value.map(Number))
    bulkDeleteConfirmOpen.value = false
    clearSelection()
    await load()
  } catch (err) {
    logApiError('admin.views.bulk-delete', err)
    bulkDeleteError.value = err instanceof Error ? err.message : 'Selected views could not be deleted.'
  } finally {
    bulkActionBusy.value = false
  }
}

const onSaved = (savedView: AdminView) => {
  const wasCreating = editingView.value === null
  drawerOpen.value = false
  void load()
  if (wasCreating) {
    router.push({ name: 'admin-view-detail', params: { id: savedView.id } })
  }
}

watch(searchInput, () => {
  if (searchDebounce) clearTimeout(searchDebounce)
  searchDebounce = setTimeout(() => {
    void load()
  }, 300)
})

watch(roleFilter, () => {
  void load()
})

watch(activeTab, () => {
  selectedIds.value = []
})

onMounted(load)
</script>

<style scoped>
.admin-views__main {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.admin-views__toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  /* With the column's 16px gap, 20px below the tabs. */
  margin-bottom: 0.25rem;
}

.admin-views__toolbar .tab-bar {
  margin-bottom: 0;
}

.admin-views__toolbar .btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

/* Beside Search in the table's search card, and drawn like it. */
.admin-views__error {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0;
  padding: 0.75rem 1rem;
  border-left: 4px solid var(--danger);
  border-radius: 6px;
  background-color: rgba(220, 53, 69, 0.08);
  color: var(--danger);
}

.admin-views__dialog-error {
  margin: 0.9rem 0 0;
  padding: 0.65rem 0.75rem;
  border-left: 3px solid var(--danger);
  border-radius: 6px;
  background-color: rgba(220, 53, 69, 0.08);
  color: var(--danger);
  font-size: 0.9rem;
  line-height: 1.4;
}
</style>
