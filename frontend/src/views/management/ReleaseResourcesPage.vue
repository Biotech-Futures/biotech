<template>
  <!-- Management > Challenge Start > Release Resources: when students, mentors
       and supervisors get each resource. Sorted by when it was released last
       year, so this year's can follow it. -->
  <section id="release-resources" class="card release-resources">
    <h3 class="release-resources__title">Release Resources</h3>
    <p class="release-resources__hint">
      Shown, a resource is open now to everyone it's for. Hidden, it appears on its Release at date, from
      the start of that day, Sydney time, and stays hidden without one. Admins always see every resource.
      Last released is when it was released last year.
    </p>

    <p v-if="error" class="release-resources__error" role="alert">{{ error }}</p>

    <AppDataTable
      v-model:search="search"
      :columns="columns"
      :rows="rows"
      row-key="id"
      :selectable="false"
      :loading="isLoading"
      search-placeholder="Resource name"
      :default-sort="{ key: 'last', direction: 'asc' }"
      :focus-row="focusResource"
      :empty-message="search.trim() ? 'No resource matches.' : 'No resources yet.'"
    >
      <!-- Each resource's icon before its name, as the Resources page has it. -->
      <template #cell-icon="{ row }">
        <i class="release-resources__icon" :class="resourceFileIcon(row)" aria-hidden="true"></i>
      </template>
      <template #cell-edit="{ row }">
        <button
          type="button"
          class="btn btn-outline btn-sm"
          :data-test="`release-edit-${row.id}`"
          @click="openEdit(Number(row.id))"
        >
          Edit
        </button>
      </template>
      <template #cell-shown="{ row }">
        <HideShowSwitch
          :on="Boolean(row.shown)"
          :disabled="savingId === row.id"
          :label="`Show ${row.name}`"
          :data-test="`release-shown-${row.id}`"
          @change="save(Number(row.id), { shown: $event })"
        />
      </template>
      <template #cell-release="{ row }">
        <AppDatePicker
          :model-value="(row.release_on as string | null)"
          class="app-input app-input--compact release-resources__date"
          :disabled="savingId === row.id"
          placeholder="No date"
          :data-test="`release-date-${row.id}`"
          @update:model-value="save(Number(row.id), { release_on: $event || null })"
        />
      </template>
    </AppDataTable>

    <!-- Edit: the Resources page's own panel. -->
    <AdminResourceFormSheet
      v-model="editOpen"
      :resource="editing"
      :busy="isDeleting"
      @saved="load"
      @delete="askDelete"
    />
    <ConfirmDialog
      :model-value="toDelete !== null"
      title="Delete resource"
      :message="`Are you sure you want to delete resource &quot;${toDelete?.resource_name ?? ''}&quot;? This action cannot be undone.`"
      confirm-label="Delete"
      busy-label="Deleting…"
      variant="danger"
      :busy="isDeleting"
      @confirm="confirmDelete"
      @update:model-value="(open) => { if (!open) toDelete = null }"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import AppDataTable, { type DataTableColumn } from '@/components/AppDataTable.vue'
import AppDatePicker from '@/components/AppDatePicker.vue'
import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import AdminResourceFormSheet from '@/components/admin/resources/AdminResourceFormSheet.vue'
import { deleteAdminResource, fetchAdminResource, type AdminResourceDetail } from '@/utils/adminAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { formatShortDate } from '@/utils/date'
import { fetchResourceReleases, saveResourceRelease, type ResourceReleaseRow } from '@/utils/managementAPI'
import { resourceFileIcon } from '@/utils/resource'
import HideShowSwitch from './HideShowSwitch.vue'

// Back from a resource's page (its Back), the resource it was: its row
// brought into view, on whichever page of the table has it.
const route = useRoute()
const focusResource = computed(() =>
  typeof route.query.resource === 'string' ? route.query.resource : undefined
)

const resources = ref<ResourceReleaseRow[]>([])
const isLoading = ref(true)
const error = ref('')
const search = ref('')
const savingId = ref<number | null>(null)

// Last year's release by its time, those with none last.
const lastTime = (row: Record<string, unknown>) =>
  row.last_released_at ? Date.parse(String(row.last_released_at)) : Number.MAX_SAFE_INTEGER

const columns: DataTableColumn[] = [
  { key: 'icon', label: '', sortable: false, cellClass: () => 'resource-icon-cell' },
  // Each name opens its resource, as the Resources page does.
  // Its page, whose Back comes back here (from=release-resources).
  {
    key: 'name',
    label: 'Name',
    primary: true,
    linkTo: (row) => ({ name: 'resource-detail', params: { id: String(row.id) }, query: { from: 'release-resources' } }),
  },
  { key: 'edit', label: 'Edit', sortable: false },
  { key: 'shown', label: 'Show/Hide', sortable: false },
  { key: 'release', label: 'Release at', sortable: false },
  { key: 'last', label: 'Last released', sortValue: lastTime }
]

const rows = computed(() => {
  const term = search.value.trim().toLowerCase()
  return resources.value
    .filter((resource) => !term || resource.name.toLowerCase().includes(term))
    .map((resource) => ({
      ...resource,
      last: resource.last_released_at ? formatShortDate(resource.last_released_at) : '—'
    }))
})

const load = async () => {
  try {
    resources.value = await fetchResourceReleases()
  } catch (err) {
    error.value = apiErrorFromUnknown(err, 'The resources could not be loaded.').message
  } finally {
    isLoading.value = false
  }
}

// Shown or hidden, or its date, saved as it's changed: its row as the server has it then.
const save = async (id: number, change: { shown?: boolean; release_on?: string | null }) => {
  savingId.value = id
  error.value = ''
  try {
    const saved = await saveResourceRelease(id, change)
    resources.value = resources.value.map((item) => (item.id === saved.id ? saved : item))
  } catch (err) {
    error.value = apiErrorFromUnknown(err, 'The change could not be saved.').message
  } finally {
    savingId.value = null
  }
}

// Editing, in the Resources page's panel, fetched whole first.
const editOpen = ref(false)
const editing = ref<AdminResourceDetail | null>(null)

const openEdit = async (id: number) => {
  error.value = ''
  try {
    editing.value = await fetchAdminResource(id)
    editOpen.value = true
  } catch (err) {
    error.value = apiErrorFromUnknown(err, 'The resource could not be opened.').message
  }
}

// Its panel's Delete, once confirmed, as on the Resources page.
const toDelete = ref<AdminResourceDetail | null>(null)
const isDeleting = ref(false)

const askDelete = () => {
  toDelete.value = editing.value
  editOpen.value = false
}

const confirmDelete = async () => {
  const resource = toDelete.value
  if (!resource || isDeleting.value) return
  isDeleting.value = true
  error.value = ''
  try {
    await deleteAdminResource(resource.id)
    resources.value = resources.value.filter((item) => item.id !== resource.id)
  } catch (err) {
    error.value = apiErrorFromUnknown(err, 'The resource could not be deleted.').message
  } finally {
    isDeleting.value = false
    toDelete.value = null
  }
}

onMounted(load)
</script>

<style scoped>
/* Laid out as Challenge Start's own card. */
.release-resources {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* The icon before each name, as the Resources page's. */
:deep(.resource-icon-cell) {
  width: 2.5rem;
  padding-right: 0;
}

.release-resources__icon {
  display: inline-block;
  width: 20px;
  color: var(--dark-green);
  text-align: center;
}

/* Headed as Pages Visibility above it: a plain title, its hint under it. */
.release-resources__title {
  font-size: 1.05rem;
  font-weight: 600;
  margin: 0;
}

.release-resources__hint {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.release-resources__error {
  margin: 0;
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  background: color-mix(in srgb, var(--danger) 12%, transparent);
  color: var(--danger);
  font-size: 0.9rem;
}

/* A date's width, in the row. */
.release-resources__date {
  width: 11rem;
  max-width: none;
}
</style>
