<template>
  <div class="admin-views-table">
    <AppDataTable
      :columns="columns"
      :rows="tableRows"
      row-key="id"
      :loading="loading"
      :selected="selected"
      :search="search"
      search-placeholder="Search views by name, description..."
      search-width="320px"
      empty-message="No views found."
      :action-columns="3"
      clickable-rows
      @update:selected="onSelectedChange"
      @update:search="emit('update:search', $event)"
      @row-click="onRowClick"
    >
      <template v-if="$slots.filters" #filters>
        <slot name="filters" />
      </template>

      <template #cell-name="{ row }">
        <div class="admin-views-table__primary">
          <strong>{{ toView(row).name }}</strong>
          <span v-if="toView(row).description" class="admin-views-table__muted">
            {{ toView(row).description }}
          </span>
        </div>
      </template>

      <!-- Edit | View | Export or Delete, so View lines up on every row.
           Default views can't be edited or deleted, but can be exported. -->
      <template #actions="{ row, column }">
        <button
          v-if="column === 0 && !toView(row).isDefault"
          type="button"
          class="btn btn-sm btn-outline"
          @click.stop="requestEdit(toView(row))"
        >
          Edit
        </button>
        <button
          v-else-if="column === 1"
          type="button"
          class="btn btn-sm btn-outline"
          @click.stop="goRun(toView(row))"
        >
          View
        </button>
        <button
          v-else-if="column === 2 && toView(row).isDefault"
          type="button"
          class="btn btn-sm btn-outline"
          @click.stop="exportCsv(toView(row))"
        >
          Export
        </button>
        <button
          v-else-if="column === 2"
          type="button"
          class="btn btn-sm btn-outline"
          @click.stop="openDelete(toView(row))"
        >
          Delete
        </button>
      </template>
    </AppDataTable>

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
import AppDataTable, { type DataTableColumn } from '@/components/AppDataTable.vue'
import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import { deleteAdminView, getAdminViewExportUrl, type AdminView } from '@/utils/adminAPI'
import { logApiError } from '@/utils/apiError'

const props = withDefaults(
  defineProps<{
    views: AdminView[]
    loading?: boolean
    selected?: Array<string | number>
    search?: string
  }>(),
  {
    loading: false,
    selected: () => []
  }
)

const emit = defineEmits<{
  (e: 'update:selected', value: Array<string | number>): void
  (e: 'update:search', value: string): void
  (e: 'edit', view: AdminView): void
  (e: 'changed'): void
}>()

const router = useRouter()

const columns: DataTableColumn[] = [{ key: 'name', label: 'View Name & Description' }]

const tableRows = computed(() => props.views as unknown as Record<string, unknown>[])
const toView = (row: Record<string, unknown>) => row as unknown as AdminView

const onSelectedChange = (value: Array<string | number>) => emit('update:selected', value)

const goRun = (view: AdminView) => {
  router.push({ name: 'admin-view-detail', params: { id: view.id } })
}

const onRowClick = (row: Record<string, unknown>) => {
  goRun(toView(row))
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
