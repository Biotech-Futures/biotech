<template>
  <!-- Known Universities: names registration treats as a university, not a
       school. Added, renamed and taken off here, every one listed at once. -->
  <section class="card known-universities">
    <div class="card-header">
      <h3 class="card-title">Known Universities</h3>
    </div>
    <p class="known-universities__hint">
      Registration asks a student to confirm their school is a school when its name matches one of
      these, ignoring case and spacing. Names containing "university" are caught without being listed.
    </p>

    <p v-if="error" class="known-universities__error" role="alert">{{ error }}</p>

    <!-- The site's table: Search in its card, Add beside it, and its pager. -->
    <AppDataTable
      v-model:search="search"
      :columns="columns"
      :rows="rows"
      row-key="id"
      :selectable="false"
      :loading="isLoading"
      search-placeholder="Search names"
      :default-sort="{ key: 'name', direction: 'asc' }"
      :empty-message="search.trim() ? 'No name matches.' : 'No universities listed yet.'"
    >
      <template #stats>
        {{ universities.length }} {{ universities.length === 1 ? 'university' : 'universities' }} listed
      </template>
      <template #search-side>
        <form class="known-universities__add" data-test="university-add" @submit.prevent="add">
          <input
            v-model="newName"
            class="known-universities__input"
            maxlength="255"
            placeholder="Add a university, e.g. USYD"
            aria-label="Add a university"
            data-test="university-new-name"
          />
          <button type="submit" class="btn btn-primary btn-sm" :disabled="isAdding || !newName.trim()">
            {{ isAdding ? 'Adding…' : 'Add' }}
          </button>
        </form>
      </template>
      <!-- Renamed in place: its name becomes a box with Save and Cancel. -->
      <template #cell-name="{ row }">
        <input
          v-if="editingId === row.id"
          v-model="editName"
          class="known-universities__input"
          maxlength="255"
          :aria-label="`New name for ${row.name}`"
          data-test="university-edit-name"
          @keydown.enter.prevent="saveRename(toUniversity(row))"
          @keydown.esc.prevent="cancelRename"
        />
        <span v-else>{{ row.name }}</span>
      </template>
      <template #actions="{ row }">
        <div class="known-universities__actions">
          <template v-if="editingId === row.id">
            <button type="button" class="btn btn-outline btn-sm" :disabled="isSaving" @click="cancelRename">
              Cancel
            </button>
            <button
              type="button"
              class="btn btn-primary btn-sm"
              :disabled="isSaving || !editName.trim()"
              data-test="university-save"
              @click="saveRename(toUniversity(row))"
            >
              {{ isSaving ? 'Saving…' : 'Save' }}
            </button>
          </template>
          <template v-else>
            <button
              type="button"
              class="btn btn-outline btn-sm"
              :data-test="`university-edit-${row.id}`"
              @click="startRename(toUniversity(row))"
            >
              Edit
            </button>
            <button
              type="button"
              class="btn btn-outline btn-sm"
              :data-test="`university-delete-${row.id}`"
              @click="toDelete = toUniversity(row)"
            >
              Delete
            </button>
          </template>
        </div>
      </template>
    </AppDataTable>

    <ConfirmDialog
      :model-value="toDelete !== null"
      title="Delete university"
      :message="`Take ${toDelete?.name ?? ''} off the list? Registration stops treating it as a university.`"
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

import AppDataTable, { type DataTableColumn } from '@/components/AppDataTable.vue'
import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import {
  addKnownUniversity,
  deleteKnownUniversity,
  fetchKnownUniversities,
  renameKnownUniversity,
  type KnownUniversity,
} from '@/utils/adminAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { formatShortDateTime } from '@/utils/date'

const columns: DataTableColumn[] = [
  { key: 'name', label: 'Name', sortValue: (row) => String(row.name).toLowerCase() },
  { key: 'added', label: 'Added', sortValue: (row) => String(toUniversity(row).createdAt ?? '') },
]

const universities = ref<KnownUniversity[]>([])
const isLoading = ref(true)
const error = ref('')
const search = ref('')

// Kept by name, as the list comes, whatever's added or renamed; the table
// sorts them as its headings are clicked.
const byName = (list: KnownUniversity[]) =>
  [...list].sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }))

// Searched as it's typed: part of a name, in any casing.
const rows = computed(() => {
  const typed = search.value.trim().toLowerCase()
  return universities.value
    .filter((university) => !typed || university.name.toLowerCase().includes(typed))
    .map((university) => ({
      id: university.id,
      name: university.name,
      added: university.createdAt ? formatShortDateTime(university.createdAt) : '—',
      university,
    }))
})
const toUniversity = (row: Record<string, unknown>) => row.university as KnownUniversity

const load = async () => {
  try {
    universities.value = byName(await fetchKnownUniversities())
  } catch (err) {
    error.value = apiErrorFromUnknown(err, 'The universities could not be loaded.').message
  } finally {
    isLoading.value = false
  }
}

// Adding: the server tidies its spacing, and refuses one already listed.
const newName = ref('')
const isAdding = ref(false)

const add = async () => {
  if (!newName.value.trim() || isAdding.value) return
  isAdding.value = true
  error.value = ''
  try {
    const added = await addKnownUniversity(newName.value)
    universities.value = byName([...universities.value, added])
    newName.value = ''
  } catch (err) {
    error.value = apiErrorFromUnknown(err, 'The university could not be added.').message
  } finally {
    isAdding.value = false
  }
}

// Renaming one at a time, in its row.
const editingId = ref<number | null>(null)
const editName = ref('')
const isSaving = ref(false)

const startRename = (university: KnownUniversity) => {
  editingId.value = university.id
  editName.value = university.name
  error.value = ''
}

const cancelRename = () => {
  editingId.value = null
  editName.value = ''
}

const saveRename = async (university: KnownUniversity) => {
  if (!editName.value.trim() || isSaving.value) return
  isSaving.value = true
  error.value = ''
  try {
    const renamed = await renameKnownUniversity(university.id, editName.value)
    universities.value = byName(universities.value.map((item) => (item.id === renamed.id ? renamed : item)))
    cancelRename()
  } catch (err) {
    error.value = apiErrorFromUnknown(err, 'The university could not be renamed.').message
  } finally {
    isSaving.value = false
  }
}

// Deleting, once confirmed.
const toDelete = ref<KnownUniversity | null>(null)
const isDeleting = ref(false)

const confirmDelete = async () => {
  const university = toDelete.value
  if (!university || isDeleting.value) return
  isDeleting.value = true
  error.value = ''
  try {
    await deleteKnownUniversity(university.id)
    universities.value = universities.value.filter((item) => item.id !== university.id)
    if (editingId.value === university.id) cancelRename()
  } catch (err) {
    error.value = apiErrorFromUnknown(err, 'The university could not be deleted.').message
  } finally {
    isDeleting.value = false
    toDelete.value = null
  }
}

onMounted(load)
</script>

<style scoped>
/* Laid out as Late Registration's cards. */
.known-universities {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.known-universities__hint {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.9rem;
}

/* Add, at the right of the table's search card: the button beside its box. */
.known-universities__add {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: 0.5rem;
}

.known-universities__add .known-universities__input {
  flex: 1 1 14rem;
  min-width: 0;
}

.known-universities__add .btn {
  flex-shrink: 0;
}

.known-universities__input {
  width: min(100%, 20rem);
  padding: 0.45rem 0.6rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  font: inherit;
  font-size: 0.9rem;
  color: var(--teal);
  background: var(--surface-elevated);
}

.known-universities__input:focus {
  outline: none;
  border-color: var(--dark-green);
}

.known-universities__actions {
  display: inline-flex;
  gap: 0.5rem;
}

.known-universities__error {
  margin: 0;
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  background: color-mix(in srgb, var(--danger) 12%, transparent);
  color: var(--danger);
  font-size: 0.9rem;
}
</style>
