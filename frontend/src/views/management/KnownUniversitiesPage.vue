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
    <p v-if="uploadSummary" class="known-universities__summary" role="status" data-test="university-upload-summary">
      {{ uploadSummary }}
    </p>

    <!-- The site's table: Search in its card, Add beside it, and its pager. -->
    <AppDataTable
      v-model:search="search"
      :columns="columns"
      :rows="rows"
      v-model:selected="selectedIds"
      row-key="id"
      :loading="isLoading"
      search-placeholder="Name, acronym or country"
      :default-sort="{ key: 'updated', direction: 'desc' }"
      :empty-message="search.trim() || countryFilter ? 'No university matches.' : 'No universities listed yet.'"
    >
      <template #filters>
        <label class="table-filter-field">
          <span class="table-filter-label">Country</span>
          <AppSelect
            v-model="countryFilter"
            class="table-filter"
            aria-label="Country"
            :options="countryOptions"
            data-test="university-country-filter"
          />
        </label>
      </template>
      <template #search-side>
        <button type="button" class="btn btn-outline btn-sm" data-test="university-upload-open" @click="openUpload">
          <i class="fas fa-upload" aria-hidden="true"></i>
          Upload Universities
        </button>
        <button type="button" class="btn btn-primary btn-sm" data-test="university-add-open" @click="openAdd">
          <i class="fas fa-plus" aria-hidden="true"></i>
          Add University
        </button>
      </template>
      <!-- Those ticked, taken off together once confirmed. -->
      <template #bulk="{ rows: picked }">
        <button
          type="button"
          class="btn btn-outline-danger btn-sm"
          data-test="university-delete-selected"
          @click="toDelete = picked.map(toUniversity)"
        >
          <i class="fas fa-trash" aria-hidden="true"></i>
          Delete selected
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
            @click="toDelete = [toUniversity(row)]"
          >
            Delete
          </button>
        </div>
      </template>
    </AppDataTable>

    <ConfirmDialog
      :model-value="toDelete !== null"
      :title="toDelete && toDelete.length > 1 ? 'Delete universities' : 'Delete university'"
      :message="deleteMessage"
      confirm-label="Delete"
      busy-label="Deleting…"
      variant="danger"
      :busy="isDeleting"
      @confirm="confirmDelete"
      @update:model-value="(open) => { if (!open) toDelete = null }"
    />

    <!-- Adding or editing, in a popup: its name, and its acronym and country if known. -->
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
          <span>Name <span class="required-mark">*</span></span>
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

    <!-- Uploading a list, in a popup laid out as Grading's Upload marks and
         My Students' Upload guardian details: the file's shape, its rules,
         Browse… and the file chosen, then Upload. -->
    <Teleport to="body">
      <div v-if="uploadOpen" class="bulk-upload__overlay" @click.self="closeUpload">
        <div
          class="bulk-upload__dialog"
          role="dialog"
          aria-modal="true"
          aria-label="Upload universities"
          data-test="university-upload-form"
        >
          <div class="bulk-upload__head">
            <h3 class="bulk-upload__title">Upload universities</h3>
            <button type="button" class="bulk-upload__close" aria-label="Close" @click="closeUpload">
              &times;
            </button>
          </div>

          <p class="bulk-upload__desc">
            .xlsx or .csv, one row per university<br />
            <code>name</code>, <code>acronym</code>, <code>country</code>
          </p>
          <p class="bulk-upload__desc">
            Column headers must match exactly and need to be in order.<br />
            Values of <code>acronym</code> and <code>country</code> can be left blank.<br />
            Extra columns and rows are ignored.
          </p>

          <div class="bulk-upload__file-row">
            <button type="button" class="bulk-upload__file-btn" @click="uploadInput?.click()">Browse…</button>
            <span class="bulk-upload__file-name">{{ uploadFile?.name || 'No file selected.' }}</span>
          </div>
          <input
            ref="uploadInput"
            type="file"
            accept=".xlsx,.csv"
            class="bulk-upload__file"
            data-test="university-upload-file"
            @change="onUploadFile"
          />

          <p v-if="uploadError" class="bulk-upload__request-error">{{ uploadError }}</p>
          <p v-if="uploadBusy === 'preview'" class="bulk-upload__desc">Previewing…</p>

          <ul v-if="uploadPreview" class="bulk-upload__checks" data-test="university-upload-checks">
            <li>
              Missing Column Header(s):
              <span :class="checkClass(uploadHeadersOk)">{{ uploadHeaderText }}</span>
            </li>
            <!-- A failed header check stops the reading, so the rest never ran. -->
            <template v-if="uploadHeadersOk">
              <li class="bulk-upload__check-gap">
                Filling In Existing Records: <strong>{{ uploadPreview.summary.filled }}</strong
                >{{ rowsSuffix(uploadPreview.filled_rows) }}
              </li>
              <li>
                Writing New Records: <strong>{{ uploadPreview.summary.added }}</strong>
              </li>
              <li>
                Already Exists: <strong>{{ uploadPreview.listed_rows.length }}</strong> <span
                  class="bulk-upload__check--bad"
                  >(Cannot be Added)</span
                >{{ rowsSuffix(uploadPreview.listed_rows) }}
              </li>
              <li>
                Repeated Names: <strong>{{ uploadPreview.repeated_rows.length }}</strong
                >{{ repeatedSuffix(uploadPreview.repeated_rows) }}
              </li>
              <li>
                Blank or Too Long: <strong>{{ uploadPreview.invalid_rows.length }}</strong
                >{{ uploadPreview.invalid_rows.length ? ` (row ${uploadPreview.invalid_rows.join(', ')})` : '' }}
              </li>
            </template>
          </ul>

          <div class="bulk-upload__footer">
            <button
              type="button"
              class="btn btn-primary btn-field"
              data-test="university-upload-submit"
              :disabled="!uploadPreview || uploadPreview.summary.errors > 0 || uploadBusy !== 'idle'"
              @click="applyUpload"
            >
              {{ uploadBusy === 'apply' ? 'Applying…' : 'Apply' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import AppDataTable, { type DataTableColumn } from '@/components/AppDataTable.vue'
import AppSelect, { type AppSelectOption } from '@/components/AppSelect.vue'
import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import {
  addKnownUniversity,
  deleteKnownUniversity,
  fetchKnownUniversities,
  renameKnownUniversity,
  uploadKnownUniversities,
  type KnownUniversity,
  type KnownUniversityUpload,
  type KnownUniversityUploadRow,
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

// Country, typed freely when adding: "australia" and " Australia" are one.
const tidyCountry = (country: string | null | undefined) => (country ?? '').trim().replace(/\s+/g, ' ')
const countryKey = (country: string | null | undefined) => tidyCountry(country).toLowerCase()

// The Country filter: All, each country listed A to Z (as its first
// university by name writes it), then No country for those without one.
const countryFilter = ref('')
const countryOptions = computed<AppSelectOption[]>(() => {
  const named = new Map<string, string>()
  for (const university of universities.value) {
    const key = countryKey(university.country)
    if (key && !named.has(key)) named.set(key, tidyCountry(university.country))
  }
  const countries = [...named].sort(([, a], [, b]) => a.localeCompare(b, undefined, { sensitivity: 'base' }))
  return [
    { value: '', label: 'All countries' },
    ...countries.map(([key, label]) => ({ value: `country:${key}`, label })),
    ...(universities.value.some((university) => !countryKey(university.country))
      ? [{ value: 'none', label: 'No country' }]
      : []),
  ]
})
// A country no university has any more (deleted or changed): back to All.
watch(countryOptions, (options) => {
  if (!options.some((option) => option.value === countryFilter.value)) countryFilter.value = ''
})
const inCountry = (university: KnownUniversity) => {
  const key = countryKey(university.country)
  if (!countryFilter.value) return true
  return countryFilter.value === 'none' ? !key : countryFilter.value === `country:${key}`
}

// In the chosen country, and searched as it's typed: part of a name, acronym
// or country, in any casing.
const rows = computed(() => {
  const typed = search.value.trim().toLowerCase()
  return universities.value
    .filter(
      (university) =>
        inCountry(university) &&
        (!typed ||
          [university.name, university.acronym, university.country].some((value) =>
            (value ?? '').toLowerCase().includes(typed)
          ))
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

// Deleting, once confirmed: one (its Delete) or those ticked (Delete selected).
const selectedIds = ref<(string | number)[]>([])
const toDelete = ref<KnownUniversity[] | null>(null)
const isDeleting = ref(false)

const deleteMessage = computed(() => {
  const picked = toDelete.value ?? []
  return picked.length === 1
    ? `Take ${picked[0]!.name} off the list? Registration stops treating it as a university.`
    : `Take these ${picked.length} universities off the list? Registration stops treating them as universities.`
})

const confirmDelete = async () => {
  const picked = toDelete.value
  if (!picked?.length || isDeleting.value) return
  isDeleting.value = true
  error.value = ''
  const results = await Promise.allSettled(picked.map((university) => deleteKnownUniversity(university.id)))
  const deleted = new Set(picked.filter((_, index) => results[index]!.status === 'fulfilled').map((u) => u.id))
  universities.value = universities.value.filter((item) => !deleted.has(item.id))
  selectedIds.value = selectedIds.value.filter((id) => !deleted.has(Number(id)))
  const failed = results.find((result): result is PromiseRejectedResult => result.status === 'rejected')
  if (failed) {
    const fallback =
      picked.length === 1 ? 'The university could not be deleted.' : 'Some universities could not be deleted.'
    error.value = apiErrorFromUnknown(failed.reason, fallback).message
  }
  isDeleting.value = false
  toDelete.value = null
}

// Uploading a list (Upload Universities), as My Students' Upload guardian
// details: picking a file previews it, and Apply loads it if nothing is
// wrong (the server reads it again then). The list is fetched again after.
const uploadOpen = ref(false)
const uploadInput = ref<HTMLInputElement | null>(null)
const uploadFile = ref<File | null>(null)
const uploadPreview = ref<KnownUniversityUpload | null>(null)
const uploadError = ref('')
const uploadSummary = ref('')
const uploadBusy = ref<'idle' | 'preview' | 'apply'>('idle')

const checkClass = (ok: boolean) => (ok ? 'bulk-upload__check--ok' : 'bulk-upload__check--bad')

const uploadHeadersOk = computed(
  () =>
    !!uploadPreview.value &&
    !uploadPreview.value.checks.missing_headers.length &&
    !uploadPreview.value.checks.header_order,
)
const uploadHeaderText = computed(() => {
  const checks = uploadPreview.value?.checks
  if (!checks) return ''
  if (checks.missing_headers.length) return checks.missing_headers.join(', ')
  return checks.header_order || 'None'
})

// " (2 - Monash University, 7 - RMIT)": each row by its number, and its name.
const rowsSuffix = (rows: KnownUniversityUploadRow[]) =>
  rows.length ? ` (${rows.map((item) => `${item.row} - ${item.name}`).join(', ')})` : ''

// " (row 2, 7 Monash University, row 5, 9 RMIT)": each name given more than
// once, with every row it's on (the first one is used).
const repeatedSuffix = (groups: KnownUniversityUpload['repeated_rows']) =>
  groups.length ? ` (${groups.map((group) => `row ${group.rows.join(', ')} ${group.name}`).join(', ')})` : ''

const resetUpload = () => {
  uploadFile.value = null
  uploadPreview.value = null
  uploadError.value = ''
  uploadBusy.value = 'idle'
  // So picking the same file again still fires a change event.
  if (uploadInput.value) uploadInput.value.value = ''
}

const openUpload = () => {
  resetUpload()
  uploadOpen.value = true
}

// Its ×, or a click beside it; not while a file's on its way.
const closeUpload = () => {
  if (uploadBusy.value !== 'idle') return
  uploadOpen.value = false
  resetUpload()
}

const onUploadFile = () => {
  uploadFile.value = uploadInput.value?.files?.[0] ?? null
  if (uploadInput.value) uploadInput.value.value = ''
  uploadPreview.value = null
  uploadError.value = ''
  if (uploadFile.value) void previewUpload()
}

const previewUpload = async () => {
  if (!uploadFile.value) return
  uploadBusy.value = 'preview'
  try {
    uploadPreview.value = await uploadKnownUniversities(uploadFile.value, true)
  } catch (err) {
    uploadError.value = `Preview failed: ${apiErrorFromUnknown(err).message}`
  } finally {
    uploadBusy.value = 'idle'
  }
}

const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`

const applyUpload = async () => {
  if (!uploadFile.value || !uploadPreview.value || uploadPreview.value.summary.errors > 0) return
  uploadBusy.value = 'apply'
  uploadError.value = ''
  try {
    const { summary, checks } = await uploadKnownUniversities(uploadFile.value, false)
    uploadSummary.value = [
      `Added ${plural(summary.added, 'university', 'universities')}`,
      summary.filled ? `filled in details for ${summary.filled}` : '',
      summary.skipped ? `skipped ${summary.skipped} already listed or blank` : '',
      checks.conflicts.length ? `left ${checks.conflicts.length} with different details as they were` : '',
    ]
      .filter(Boolean)
      .join(', ')
      .concat('.')
    uploadBusy.value = 'idle'
    uploadOpen.value = false
    resetUpload()
    await load()
  } catch (err) {
    uploadBusy.value = 'idle'
    uploadError.value = `Apply failed: ${apiErrorFromUnknown(err).message}`
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

/* What an upload did, as the error is shown but green. */
.known-universities__summary {
  margin: 0;
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  background: color-mix(in srgb, var(--dark-green) 10%, transparent);
  color: var(--dark-green);
  font-size: 0.9rem;
}

/* Upload universities: Grading's Upload marks dialog (BulkUploadDialog), as
   My Students' Upload guardian details has it. */
.bulk-upload__overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  z-index: 2000;
}

.bulk-upload__dialog {
  background: var(--surface-elevated);
  color: var(--teal);
  border-radius: 10px;
  box-shadow: 0 10px 40px var(--shadow);
  width: 100%;
  max-width: 42rem;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  max-height: 90vh;
  overflow: auto;
}

.bulk-upload__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.bulk-upload__title {
  margin: 0;
  font-size: 1.15rem;
}

.bulk-upload__close {
  border: none;
  background: none;
  font-size: 1.5rem;
  line-height: 1;
  color: var(--text-muted);
  cursor: pointer;
}

.bulk-upload__close:hover {
  color: var(--teal);
}

.bulk-upload__desc {
  color: var(--text-muted);
  font-size: 0.88rem;
  margin: 0;
}

.bulk-upload__desc code {
  background: var(--bg-light);
  border-radius: 4px;
  padding: 0.05rem 0.3rem;
  font-size: 0.82rem;
}

/* The native input is hidden; only Browse… opens the file picker. */
.bulk-upload__file {
  display: none;
}

.bulk-upload__file-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.bulk-upload__file-btn {
  background-color: transparent;
  color: var(--dark-green);
  border: 1px solid var(--border-light);
  border-radius: 4px;
  padding: 0.3rem 0.7rem;
  font-size: 0.84rem;
  font-weight: 500;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.3s ease;
}

.bulk-upload__file-btn:hover {
  background-color: var(--light-green);
  border-color: var(--dark-green);
}

.bulk-upload__file-name {
  color: var(--text-muted);
  font-size: 0.85rem;
}

.bulk-upload__request-error {
  color: var(--danger);
  font-size: 0.88rem;
  margin: 0;
}

.bulk-upload__checks {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.85rem;
}

/* Blank line between the checks and the record counts. */
.bulk-upload__check-gap {
  margin-top: 0.65rem;
}

.bulk-upload__check--ok {
  color: var(--dark-green);
  font-weight: 600;
}

.bulk-upload__check--bad {
  color: var(--danger);
  font-weight: 600;
}

.bulk-upload__footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}
</style>
