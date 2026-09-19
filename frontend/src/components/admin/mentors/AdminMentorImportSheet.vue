<template>
  <FormSheet
    :model-value="modelValue"
    title="Import Mentors CSV"
    description="Upload a mentor registration export, review valid and skipped rows, then import mentors."
    width="min(100vw, 720px)"
    @close="onDismiss"
  >
    <div class="mentor-import">
      <section class="mentor-import__section">
        <div class="mentor-import__file-row">
          <label class="form-label" for="mentor-csv-file">CSV file</label>
          <button
            type="button"
            class="btn btn-sm btn-outline"
            :disabled="importing"
            @click="downloadTemplate"
          >
            <i class="fas fa-download" aria-hidden="true"></i>
            <span>Download template</span>
          </button>
        </div>
        <input
          id="mentor-csv-file"
          ref="fileInput"
          class="form-input"
          type="file"
          accept=".csv,text/csv"
          :disabled="importing"
          @change="onFileChange"
        />
        <p v-if="fileName" class="mentor-import__hint">{{ fileName }}</p>
        <p v-else-if="!result" class="mentor-import__hint">Select a CSV file to continue.</p>
      </section>

      <p v-if="fileError" class="mentor-import__error" role="alert">
        {{ fileError }}
      </p>

      <p v-if="submitError" class="mentor-import__error" role="alert">
        {{ submitError }}
      </p>

      <section v-if="hasParsedRows" class="mentor-import__summary" aria-live="polite">
        <span v-if="validRows.length > 0" class="mentor-import__badge mentor-import__badge--ready">
          {{ validRows.length }} ready
        </span>
        <span v-else class="mentor-import__summary-message">
          No valid rows to import - check the skipped list below.
        </span>
        <span v-if="invalidRows.length" class="mentor-import__badge">
          {{ invalidRows.length }} skipped
        </span>
      </section>

      <section v-if="validRows.length" class="mentor-import__section">
        <div class="mentor-import__section-head">
          <h3>Preview</h3>
          <span>{{ validRows.length }} valid row{{ validRows.length === 1 ? '' : 's' }}</span>
        </div>
        <div class="mentor-import__preview-list">
          <article
            v-for="(row, index) in previewRows"
            :key="`${row.email}-${index}`"
            class="mentor-import__preview-row"
          >
            <div class="mentor-import__primary">
              <strong>{{ row.firstName }} {{ row.lastName }}</strong>
              <span>{{ row.email }}</span>
              <small v-if="row.backgroundNote">{{ row.backgroundNote }}</small>
            </div>
            <div class="mentor-import__chips">
              <span>{{ row.state ? `${row.country} / ${row.state}` : row.country }}</span>
              <span>{{ row.mentorBackground ?? 'No background' }}</span>
              <span>Cap {{ row.mentorMaxGroupCount }}</span>
              <span>{{ row.interests.length }} interest{{ row.interests.length === 1 ? '' : 's' }}</span>
            </div>
          </article>
          <p v-if="validRows.length > PREVIEW_LIMIT" class="mentor-import__hint">
            Showing first {{ PREVIEW_LIMIT }} rows.
          </p>
        </div>
      </section>

      <section v-if="invalidRows.length" class="mentor-import__section">
        <div class="mentor-import__section-head">
          <h3>Skipped before import</h3>
          <span>{{ invalidRows.length }} row{{ invalidRows.length === 1 ? '' : 's' }}</span>
        </div>
        <div class="mentor-import__invalid-list">
          <div
            v-for="row in invalidRows"
            :key="`${row.rowNumber}-${row.email}`"
            class="mentor-import__invalid-row"
          >
            <span>Row {{ row.rowNumber }} - {{ row.email }}</span>
            <strong>{{ row.reason }}</strong>
          </div>
        </div>
      </section>

      <section
        v-if="result"
        class="mentor-import__result"
        :class="{ 'mentor-import__result--success': !submitError }"
        aria-live="polite"
      >
        <div class="mentor-import__section-head">
          <h3>Import complete</h3>
          <span>{{ result.data.created.length }} created</span>
        </div>
        <p class="mentor-import__hint">{{ result.msg }}</p>

        <div v-if="result.data.skipped.length" class="mentor-import__invalid-list">
          <div
            v-for="(row, index) in result.data.skipped"
            :key="`${row.email}-${index}`"
            class="mentor-import__invalid-row"
          >
            <span>{{ row.email }}</span>
            <strong>{{ row.reason }}</strong>
          </div>
        </div>
      </section>
    </div>

    <template #footer>
      <button
        type="button"
        class="btn btn-outline"
        :disabled="importing"
        @click="onDismiss"
      >
        {{ result ? 'Close' : 'Cancel' }}
      </button>
      <button
        v-if="!result"
        type="button"
        class="btn btn-primary mentor-import__submit"
        :disabled="!canImport"
        @click="runImport"
      >
        <span v-if="importing" class="mentor-import__spinner" aria-hidden="true"></span>
        {{ importing ? 'Importing...' : `Import ${validRows.length || ''} mentor${validRows.length === 1 ? '' : 's'}` }}
      </button>
    </template>
  </FormSheet>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import FormSheet from '@/components/admin/FormSheet.vue'
import { importAdminMentors, type MentorBulkImportResult } from '@/utils/adminAPI'
import {
  MENTOR_CSV_TEMPLATE,
  parseMentorCsv,
  type MentorImportRow
} from '@/utils/adminMentorCsv'
import type { ImportRowError } from '@/utils/adminStudentCsv'
import { logApiError } from '@/utils/apiError'

const PREVIEW_LIMIT = 10

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'imported', result: MentorBulkImportResult): void
}>()

const fileInput = ref<HTMLInputElement | null>(null)
const fileName = ref('')
const fileError = ref('')
const submitError = ref('')
const importing = ref(false)
const validRows = ref<MentorImportRow[]>([])
const invalidRows = ref<ImportRowError[]>([])
const result = ref<MentorBulkImportResult | null>(null)

const hasParsedRows = computed(() => validRows.value.length > 0 || invalidRows.value.length > 0)
const previewRows = computed(() => validRows.value.slice(0, PREVIEW_LIMIT))
const canImport = computed(() => validRows.value.length > 0 && !importing.value && !result.value)

const reset = () => {
  fileName.value = ''
  fileError.value = ''
  submitError.value = ''
  validRows.value = []
  invalidRows.value = []
  result.value = null
  if (fileInput.value) fileInput.value.value = ''
}

const onDismiss = () => {
  if (importing.value) return
  reset()
  emit('update:modelValue', false)
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) reset()
  }
)

const onFileChange = async (event: Event) => {
  const file = (event.target as HTMLInputElement).files?.[0] ?? null
  fileName.value = file?.name ?? ''
  fileError.value = ''
  submitError.value = ''
  validRows.value = []
  invalidRows.value = []
  result.value = null
  if (!file) return

  try {
    const parsed = parseMentorCsv(await file.text())
    validRows.value = parsed.valid
    invalidRows.value = parsed.invalid
  } catch (parseError) {
    fileError.value =
      parseError instanceof Error ? parseError.message : 'Failed to parse the CSV file.'
  }
}

const csvCell = (value: string) => {
  if (/[",\r\n]/.test(value)) return `"${value.replace(/"/g, '""')}"`
  return value
}

const downloadTemplate = () => {
  const csv = [
    MENTOR_CSV_TEMPLATE.headers.map(csvCell).join(','),
    MENTOR_CSV_TEMPLATE.sampleRow.map(csvCell).join(',')
  ].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = MENTOR_CSV_TEMPLATE.fileName
  link.click()
  URL.revokeObjectURL(url)
}

const runImport = async () => {
  if (!canImport.value) return
  importing.value = true
  submitError.value = ''
  result.value = null
  try {
    const importResult = await importAdminMentors(validRows.value)
    result.value = importResult
    emit('imported', importResult)
  } catch (importError) {
    logApiError('admin.mentors.csv-import', importError)
    submitError.value =
      importError instanceof Error ? importError.message : 'Mentors could not be imported.'
  } finally {
    importing.value = false
  }
}
</script>

<style scoped>
.mentor-import {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.mentor-import__section,
.mentor-import__summary,
.mentor-import__result {
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--white);
  padding: 1rem;
}

.mentor-import__file-row,
.mentor-import__section-head,
.mentor-import__summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.mentor-import__section-head h3 {
  margin: 0;
  font-size: 0.95rem;
}

.mentor-import__section-head span {
  color: var(--text-muted);
  font-size: 0.85rem;
}

.mentor-import__hint {
  margin: 0.45rem 0 0;
  color: var(--text-muted);
  font-size: 0.85rem;
}

.mentor-import__error {
  margin: 0;
  padding: 0.7rem 0.9rem;
  border-left: 4px solid var(--danger);
  border-radius: 6px;
  background-color: rgba(220, 53, 69, 0.08);
  color: var(--danger);
  font-size: 0.875rem;
}

.mentor-import__badge {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0.2rem 0.55rem;
  border: 1px solid var(--border-light);
  border-radius: 999px;
  background-color: var(--bg-light);
  color: var(--text-muted);
  font-size: 0.75rem;
  font-weight: 600;
}

.mentor-import__badge--ready {
  border-color: rgba(1, 113, 81, 0.3);
  background-color: rgba(1, 113, 81, 0.08);
  color: var(--dark-green);
}

.mentor-import__summary-message {
  color: var(--text-muted);
  font-size: 0.875rem;
  font-weight: 600;
}

.mentor-import__preview-list,
.mentor-import__invalid-list,
.mentor-import__co-registration {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  margin-top: 0.75rem;
}

.mentor-import__preview-row,
.mentor-import__invalid-row {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.75rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--bg-light);
}

.mentor-import__primary {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.mentor-import__primary span,
.mentor-import__primary small,
.mentor-import__invalid-row span {
  color: var(--text-muted);
  font-size: 0.85rem;
}

.mentor-import__chips {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  align-content: flex-start;
  gap: 0.35rem;
}

.mentor-import__chips span {
  padding: 0.15rem 0.45rem;
  border-radius: 999px;
  background-color: var(--white);
  border: 1px solid var(--border-light);
  color: var(--text-muted);
  font-size: 0.75rem;
  font-weight: 600;
}

.mentor-import__invalid-row {
  flex-direction: column;
  background-color: rgba(220, 53, 69, 0.05);
}

.mentor-import__invalid-row strong {
  color: var(--danger);
  font-size: 0.85rem;
}

.mentor-import__result--success {
  border-color: rgba(1, 113, 81, 0.35);
  background-color: rgba(1, 113, 81, 0.04);
}

.mentor-import__submit:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.mentor-import__submit:disabled:hover {
  transform: none;
  box-shadow: none;
}

.mentor-import__spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.45);
  border-top-color: var(--white);
  border-radius: 50%;
  display: inline-block;
  margin-right: 0.4rem;
  animation: mentor-import-spin 0.8s linear infinite;
}

@keyframes mentor-import-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 640px) {
  .mentor-import__preview-row {
    flex-direction: column;
  }

  .mentor-import__chips {
    justify-content: flex-start;
  }
}
</style>
