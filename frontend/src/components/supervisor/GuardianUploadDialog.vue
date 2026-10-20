<template>
  <button type="button" class="btn btn-outline btn-sm" @click="openDialog">
    <i class="fas fa-upload" aria-hidden="true"></i> Upload Guardian Details
  </button>

  <Teleport to="body">
    <div v-if="open" class="bulk-upload__overlay" @click.self="closeDialog">
      <div class="bulk-upload__dialog" role="dialog" aria-modal="true" aria-label="Upload guardian details">
        <div class="bulk-upload__head">
          <h3 class="bulk-upload__title">Upload guardian details</h3>
          <button type="button" class="bulk-upload__close" aria-label="Close" @click="closeDialog">
            &times;
          </button>
        </div>

        <p class="bulk-upload__desc">
          .xlsx or .csv, one row per student<br />
          <code>student_email</code>, <code>guardian_first_name</code>, <code>guardian_last_name</code>,
          <code>guardian_email</code>
        </p>
        <p class="bulk-upload__desc">
          Column headers must match exactly and need to be in order.<br />
          Each <code>student_email</code> must be one of your students.<br />
          Extra columns and rows are ignored.
        </p>

        <div class="bulk-upload__file-row">
          <button type="button" class="bulk-upload__file-btn" @click="fileInput?.click()">Browse…</button>
          <span class="bulk-upload__file-name">{{ file?.name || 'No file selected.' }}</span>
        </div>
        <input ref="fileInput" type="file" accept=".xlsx,.csv" class="bulk-upload__file" @change="onFileChange" />

        <p v-if="requestError" class="bulk-upload__request-error">{{ requestError }}</p>
        <p v-if="busy === 'preview'" class="bulk-upload__desc">Previewing…</p>

        <ul v-if="preview" class="bulk-upload__checks">
          <li>
            Missing Column Header(s):
            <span :class="checkClass(headersOk)">{{ headerText }}</span>
          </li>
          <!-- A failed header check stops the reading, so the rest never ran. -->
          <template v-if="headersOk">
            <li>
              Students not on your list:
              <span :class="checkClass(!preview.checks.unknown_students.length)">{{ unknownText }}</span>
            </li>
            <li>
              Incorrect guardian details:
              <span :class="checkClass(!preview.checks.bad_rows.length)">{{ badRowsText }}</span>
            </li>
            <li v-if="preview.checks.consented.length">
              Permission already given:
              <span class="bulk-upload__check--bad">{{ consentedText }}</span>
            </li>
            <template v-if="!preview.summary.errors">
              <li class="bulk-upload__check-gap">
                Overwriting Existing Records:
                <strong :class="preview.updates.length ? 'bulk-upload__count--overwrite' : 'bulk-upload__check--ok'">
                  {{ preview.updates.length }}</strong
                >{{ namesSuffix(preview.updates) }}
              </li>
              <li>
                Writing New Records: <strong>{{ preview.creates.length }}</strong>
              </li>
            </template>
          </template>
        </ul>

        <div class="bulk-upload__footer">
          <button
            type="button"
            class="btn btn-primary btn-sm"
            :disabled="!preview || preview.summary.errors > 0 || busy !== 'idle'"
            @click="doApply"
          >
            {{ busy === 'apply' ? 'Applying…' : 'Apply' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { apiErrorFromUnknown } from '@/utils/apiError'
import {
  uploadGuardianDetails,
  type GuardianUploadEntry,
  type GuardianUploadResult,
} from '@/utils/supervisedStudents'

// Grading's Upload marks, for guardians: picking a file previews it, and
// Apply saves it if nothing is wrong. The server reads the file again on
// Apply, so it acts on the students as they are then.
const emit = defineEmits<{
  // How many students' guardians were saved.
  applied: [saved: number]
}>()

const open = ref(false)
const file = ref<File | null>(null)
const preview = ref<GuardianUploadResult | null>(null)
const requestError = ref('')
const busy = ref<'idle' | 'preview' | 'apply'>('idle')
const fileInput = ref<HTMLInputElement | null>(null)

const checkClass = (ok: boolean) => (ok ? 'bulk-upload__check--ok' : 'bulk-upload__check--bad')

const headersOk = computed(
  () => !!preview.value && !preview.value.checks.missing_headers.length && !preview.value.checks.header_order,
)
const headerText = computed(() => {
  const checks = preview.value?.checks
  if (!checks) return ''
  if (checks.missing_headers.length) return checks.missing_headers.join(', ')
  return checks.header_order || 'None'
})
const rowsText = (rows: { row: number; email?: string; reason?: string }[]) =>
  rows.length ? rows.map((item) => `row ${item.row} (${item.reason ?? item.email})`).join(', ') : 'None'
const unknownText = computed(() => rowsText(preview.value?.checks.unknown_students ?? []))
const badRowsText = computed(() => rowsText(preview.value?.checks.bad_rows ?? []))
const consentedText = computed(() => rowsText(preview.value?.checks.consented ?? []))

// " (Aarav Gupta, Mia Chen)": whose guardian is replaced.
const namesSuffix = (entries: GuardianUploadEntry[]) =>
  entries.length ? ` (${entries.map((entry) => entry.student_name).join(', ')})` : ''

const reset = () => {
  file.value = null
  preview.value = null
  requestError.value = ''
  busy.value = 'idle'
  // So picking the same file again still fires a change event.
  if (fileInput.value) fileInput.value.value = ''
}

const openDialog = () => {
  reset()
  open.value = true
}

const closeDialog = () => {
  if (busy.value !== 'idle') return
  open.value = false
  reset()
}

const onFileChange = () => {
  file.value = fileInput.value?.files?.[0] ?? null
  if (fileInput.value) fileInput.value.value = ''
  preview.value = null
  requestError.value = ''
  if (file.value) void doPreview()
}

const doPreview = async () => {
  if (!file.value) return
  busy.value = 'preview'
  try {
    preview.value = await uploadGuardianDetails(file.value, true)
  } catch (err) {
    requestError.value = `Preview failed: ${apiErrorFromUnknown(err).message}`
  } finally {
    busy.value = 'idle'
  }
}

const doApply = async () => {
  if (!file.value || !preview.value || preview.value.summary.errors > 0) return
  busy.value = 'apply'
  requestError.value = ''
  try {
    const data = await uploadGuardianDetails(file.value, false)
    busy.value = 'idle'
    open.value = false
    emit('applied', data.saved ?? 0)
    reset()
  } catch (err) {
    busy.value = 'idle'
    requestError.value = `Apply failed: ${apiErrorFromUnknown(err).message}`
  }
}
</script>

<style scoped>
/* Grading's Upload marks dialog (BulkUploadDialog). */
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

/* Overwrites are the risky half of an apply, so their count is amber. */
.bulk-upload__count--overwrite {
  color: #eab308;
}

.bulk-upload__footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}
</style>
