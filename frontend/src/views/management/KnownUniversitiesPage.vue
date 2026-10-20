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
      search-placeholder="Name, acronym or country"
      :default-sort="{ key: 'updated', direction: 'desc' }"
      :empty-message="search.trim() ? 'No university matches.' : 'No universities listed yet.'"
    >
      <template #stats>
        {{ universities.length }} {{ universities.length === 1 ? 'university' : 'universities' }} listed
      </template>
      <template #search-side>
        <button type="button" class="btn btn-primary btn-sm" data-test="university-add-open" @click="openAdd">
          <i class="fas fa-plus" aria-hidden="true"></i>
          Add University
        </button>
      </template>
      <template #actions="{ row }">
        <div class="known-universities__actions">
          <button
            type="button"
            class="btn btn-outline btn-sm"
            :data-test="`university-edit-${row.id}`"
            @click="openEdit(toUniversity(row))"
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

    <!-- Adding or editing, in a popup: its full name, and its acronym and country if known. -->
    <ConfirmDialog
      v-model="formOpen"
      :title="editingId === null ? 'Add university' : 'Edit university'"
      :confirm-label="editingId === null ? 'Add' : 'Save'"
      :busy-label="editingId === null ? 'Adding…' : 'Saving…'"
      :busy="isSaving"
      :disabled="!draft.name.trim()"
      @confirm="save"
    >
      <form class="known-universities__form" data-test="university-form" @submit.prevent="save" @keydown.enter.prevent="save">
        <label class="known-universities__field">
          <span>Full name <span class="required-mark">*</span></span>
          <input
            v-model="draft.name"
            class="app-input app-input--wide"
            maxlength="255"
            placeholder="e.g. The University of Sydney"
            data-test="university-name"
          />
        </label>
        <label class="known-universities__field">
          <span>Acronym</span>
          <input v-model="draft.acronym" class="app-input" maxlength="64" placeholder="e.g. USYD" data-test="university-acronym" />
        </label>
        <label class="known-universities__field">
          <span>Country</span>
          <input v-model="draft.country" class="app-input" maxlength="100" placeholder="e.g. Australia" data-test="university-country" />
        </label>
        <p v-if="formError" class="known-universities__form-error" role="alert">{{ formError }}</p>
      </form>
    </ConfirmDialog>
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
import { formatShortDate, getSetTimeZone, toTimeZoneDateKey } from '@/utils/date'

const columns: DataTableColumn[] = [
  { key: 'name', label: 'Name', sortValue: (row) => String(row.name).toLowerCase() },
  { key: 'acronym', label: 'Acronym', sortValue: (row) => String(toUniversity(row).acronym ?? '').toLowerCase() },
  { key: 'country', label: 'Country', sortValue: (row) => String(toUniversity(row).country ?? '').toLowerCase() },
  // By the day it was last changed; the same day keeps the rows' order by name.
  { key: 'updated', label: 'Updated', sortValue: (row) => updatedDay(toUniversity(row)) },
]

// When it was last changed (when it was added, for one never changed).
const updatedOn = (university: KnownUniversity) => university.updatedAt ?? university.createdAt
const updatedDay = (university: KnownUniversity) => toTimeZoneDateKey(updatedOn(university), getSetTimeZone())

const universities = ref<KnownUniversity[]>([])
const isLoading = ref(true)
const error = ref('')
const search = ref('')

// Kept by name, as the list comes, whatever's added or renamed; the table
// sorts them as its headings are clicked.
const byName = (list: KnownUniversity[]) =>
  [...list].sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }))

// Searched as it's typed: part of a name, acronym or country, in any casing.
const rows = computed(() => {
  const typed = search.value.trim().toLowerCase()
  return universities.value
    .filter(
      (university) =>
        !typed ||
        [university.name, university.acronym, university.country].some((value) =>
          (value ?? '').toLowerCase().includes(typed)
        )
    )
    .map((university) => ({
      id: university.id,
      name: university.name,
      acronym: university.acronym || '—',
      country: university.country || '—',
      updated: updatedOn(university) ? formatShortDate(updatedOn(university)) : '—',
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

// Adding or editing, in a popup: the server tidies the spacing, and refuses
// a name already listed (said in the popup, keeping what's typed).
const emptyDraft = () => ({ name: '', acronym: '', country: '' })
const formOpen = ref(false)
const editingId = ref<number | null>(null)
const draft = ref(emptyDraft())
const formError = ref('')
const isSaving = ref(false)

const openAdd = () => {
  editingId.value = null
  draft.value = emptyDraft()
  formError.value = ''
  formOpen.value = true
}

const openEdit = (university: KnownUniversity) => {
  editingId.value = university.id
  draft.value = { name: university.name, acronym: university.acronym ?? '', country: university.country ?? '' }
  formError.value = ''
  formOpen.value = true
}

const save = async () => {
  if (!draft.value.name.trim() || isSaving.value) return
  isSaving.value = true
  formError.value = ''
  const id = editingId.value
  try {
    if (id === null) {
      const added = await addKnownUniversity({ ...draft.value })
      universities.value = byName([...universities.value, added])
    } else {
      const saved = await renameKnownUniversity(id, { ...draft.value })
      universities.value = byName(universities.value.map((item) => (item.id === saved.id ? saved : item)))
    }
    formOpen.value = false
  } catch (err) {
    const fallback = id === null ? 'The university could not be added.' : 'The university could not be saved.'
    formError.value = apiErrorFromUnknown(err, fallback).message
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

/* The Add popup's three boxes, one under another. */
.known-universities__form {
  display: grid;
  gap: 0.9rem;
  margin-top: 0.75rem;
  text-align: left;
}

.known-universities__field {
  display: grid;
  gap: 0.35rem;
  color: var(--teal);
  font-size: 0.9rem;
  font-weight: 600;
}

.known-universities__form-error {
  margin: 0;
  color: var(--danger);
  font-size: 0.9rem;
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
