<template>
  <div class="admin-views-table">
    <AdminDataTable
      :columns="columns"
      :rows="tableRows"
      row-key="id"
      :loading="loading"
      selectable
      :selected="selected"
      :show-pagination="false"
      empty-message="No views found."
      select-all-label="Select all views"
      @update:selected="onSelectedChange"
    >
      <template #cell-name="{ row }">
        <div class="admin-views-table__primary">
          <strong>{{ toView(row).name }}</strong>
          <span v-if="toView(row).description" class="admin-views-table__muted">
            {{ toView(row).description }}
          </span>
        </div>
      </template>

      <template #cell-roles="{ row }">
        <div class="admin-views-table__badges">
          <span
            v-for="role in rolesFor(toView(row))"
            :key="role"
            class="admin-views-table__badge"
          >
            {{ role }}
          </span>
        </div>
      </template>

      <template #cell-lastRun="{ row }">
        <span class="admin-views-table__muted">{{ lastRunLabel(toView(row)) }}</span>
      </template>

      <template #cell-actions="{ row }">
        <div class="admin-views-table__actions">
          <button type="button" class="btn btn-sm btn-outline" @click.stop="goRun(toView(row))">
            Run
          </button>
          <button
            v-if="toView(row).isDefault"
            type="button"
            class="btn btn-sm btn-outline"
            @click.stop="exportCsv(toView(row))"
          >
            Export
          </button>
          <template v-else>
            <button type="button" class="btn btn-sm btn-outline" @click.stop="requestEdit(toView(row))">
              Edit
            </button>
            <button type="button" class="btn btn-sm btn-outline" @click.stop="openDelete(toView(row))">
              Delete
            </button>
          </template>
        </div>
      </template>
    </AdminDataTable>

    <ConfirmDialog
      v-model="deleteConfirmOpen"
      title="Delete view"
      :message="deleteMessage"
      confirm-label="Delete"
      variant="danger"
      :busy="deleteBusy"
      @confirm="confirmDelete"
      @cancel="cancelDelete"
    >
      <p v-if="deleteError" class="admin-views-table__dialog-error" role="alert">{{ deleteError }}</p>
    </ConfirmDialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import AdminDataTable, { type AdminColumn } from '@/components/admin/AdminDataTable.vue'
import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import { deleteAdminView, getAdminViewExportUrl, type AdminView } from '@/utils/adminAPI'
import { logApiError } from '@/utils/apiError'
import { formatDateAU } from '@/utils/date'
import { roleLabel } from '@/utils/userFormat'

const props = withDefaults(
  defineProps<{
    views: AdminView[]
    loading?: boolean
    selected?: Array<string | number>
  }>(),
  {
    loading: false,
    selected: () => []
  }
)

const emit = defineEmits<{
  (e: 'update:selected', value: Array<string | number>): void
  (e: 'edit', view: AdminView): void
  (e: 'changed'): void
}>()

const router = useRouter()

const columns: AdminColumn[] = [
  { key: 'name', label: 'View Name & Description' },
  { key: 'roles', label: 'Filter Summary / Roles' },
  { key: 'lastRun', label: 'Last Run / Updated' },
  { key: 'actions', label: 'Actions', align: 'right' }
]

const tableRows = computed(() => props.views as unknown as Record<string, unknown>[])
const toView = (row: Record<string, unknown>) => row as unknown as AdminView

const rolesFor = (view: AdminView): string[] => {
  const roles = view.targetRoles || []
  if (!roles.length || roles.includes('all')) return ['All roles']
  return roles.map((role) => roleLabel(role))
}

const lastRunLabel = (view: AdminView): string => {
  if (view.lastRunAt) return `Run ${formatDateAU(view.lastRunAt)}`
  if (view.updatedAt) return `Updated ${formatDateAU(view.updatedAt)}`
  return '—'
}

const onSelectedChange = (value: Array<string | number>) => emit('update:selected', value)

const goRun = (view: AdminView) => {
  router.push({ name: 'admin-view-detail', params: { id: view.id } })
}

const exportCsv = (view: AdminView) => {
  window.open(getAdminViewExportUrl(view.id), '_blank')
}

const requestEdit = (view: AdminView) => emit('edit', view)

const deleteTarget = ref<AdminView | null>(null)
const deleteConfirmOpen = ref(false)
const deleteBusy = ref(false)
const deleteError = ref('')

const deleteMessage = computed(() =>
  deleteTarget.value
    ? `Delete "${deleteTarget.value.name}"? This cannot be undone.`
    : 'Delete this view? This cannot be undone.'
)

const openDelete = (view: AdminView) => {
  deleteTarget.value = view
  deleteError.value = ''
  deleteConfirmOpen.value = true
}

const cancelDelete = () => {
  deleteConfirmOpen.value = false
  deleteTarget.value = null
  deleteError.value = ''
}

const confirmDelete = async () => {
  if (!deleteTarget.value || deleteBusy.value) return
  deleteBusy.value = true
  deleteError.value = ''
  try {
    await deleteAdminView(deleteTarget.value.id)
    deleteConfirmOpen.value = false
    deleteTarget.value = null
    emit('changed')
  } catch (err) {
    logApiError('admin.views.delete', err)
    deleteError.value = err instanceof Error ? err.message : 'View could not be deleted.'
  } finally {
    deleteBusy.value = false
  }
}
</script>

<style scoped>
.admin-views-table__primary {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.admin-views-table__muted {
  color: var(--text-muted);
}

.admin-views-table__badges {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.admin-views-table__badge {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0.15rem 0.5rem;
  border: 1px solid var(--border-light);
  border-radius: 999px;
  background-color: var(--bg-light);
  color: var(--text-muted);
  font-size: 0.72rem;
  font-weight: 600;
}

.admin-views-table__actions {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.4rem;
}

.admin-views-table__dialog-error {
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
