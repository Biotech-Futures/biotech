<template>
  <FormSheet
    :model-value="modelValue"
    title="Import Students CSV"
    description="Upload a student registration export, review valid and skipped rows, then import students."
    width="min(100vw, 720px)"
    @close="onDismiss"
  >
    <div class="student-import">
      <section class="student-import__section">
        <div class="student-import__file-row">
          <label class="form-label" for="student-csv-file">CSV file</label>
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
          id="student-csv-file"
          ref="fileInput"
          class="form-input"
          type="file"
          accept=".csv,text/csv"
          :disabled="importing"
          @change="onFileChange"
        />
        <p v-if="fileName" class="student-import__hint">{{ fileName }}</p>
        <p v-else-if="!result" class="student-import__hint">Select a CSV file to continue.</p>
      </section>

      <p v-if="fileError" class="student-import__error" role="alert">
        {{ fileError }}
      </p>

      <p v-if="submitError" class="student-import__error" role="alert">
        {{ submitError }}
      </p>

      <section v-if="hasParsedRows" class="student-import__summary" aria-live="polite">
        <span v-if="validRows.length > 0" class="student-import__badge student-import__badge--ready">
          {{ validRows.length }} ready
        </span>
        <span v-else class="student-import__summary-message">
          No valid rows to import — check the skipped list below.
        </span>
        <span v-if="invalidRows.length" class="student-import__badge">
          {{ invalidRows.length }} skipped
        </span>
      </section>

      <section v-if="validRows.length" class="student-import__section">
        <div class="student-import__section-head">
          <h3>Preview</h3>
          <span>{{ validRows.length }} valid row{{ validRows.length === 1 ? '' : 's' }}</span>
        </div>
        <div class="student-import__preview-list">
          <article
            v-for="(row, index) in previewRows"
            :key="`${row.email}-${index}`"
            class="student-import__preview-row"
          >
            <div class="student-import__primary">
              <strong>{{ row.firstName }} {{ row.lastName }}</strong>
              <span>{{ row.email }}</span>
              <small v-if="!row.active">No approval yet - imports inactive</small>
            </div>
            <div class="student-import__chips">
              <span>{{ row.state ? `${row.country} / ${row.state}` : row.country }}</span>
              <span>Yr {{ row.yearLevel }}</span>
              <span>{{ row.interests.length }} interest{{ row.interests.length === 1 ? '' : 's' }}</span>
              <span v-if="row.supervisorEmail">Has supervisor</span>
              <span v-if="row.groupNumber">Group {{ row.groupNumber }}</span>
            </div>
          </article>
          <p v-if="validRows.length > PREVIEW_LIMIT" class="student-import__hint">
            Showing first {{ PREVIEW_LIMIT }} rows.
          </p>
        </div>
      </section>

      <section v-if="invalidRows.length" class="student-import__section">
        <div class="student-import__section-head">
          <h3>Skipped before import</h3>
          <span>{{ invalidRows.length }} row{{ invalidRows.length === 1 ? '' : 's' }}</span>
        </div>
        <div class="student-import__invalid-list">
          <div
            v-for="row in invalidRows"
            :key="`${row.rowNumber}-${row.email}`"
            class="student-import__invalid-row"
          >
            <span>Row {{ row.rowNumber }} - {{ row.email }}</span>
            <strong>{{ row.reason }}</strong>
          </div>
        </div>
      </section>

      <section
        v-if="result"
        class="student-import__result"
        :class="{ 'student-import__result--success': !submitError }"
        aria-live="polite"
      >
        <div class="student-import__section-head">
          <h3>Import complete</h3>
          <span>{{ result.data.created.length }} created</span>
        </div>
        <p class="student-import__hint">{{ result.msg }}</p>

        <div v-if="result.data.skipped.length" class="student-import__invalid-list">
          <div
            v-for="(row, index) in result.data.skipped"
            :key="`${row.email}-${index}`"
            class="student-import__invalid-row"
          >
            <span>{{ row.email }}</span>
            <strong>{{ row.reason }}</strong>
          </div>
        </div>

        <div v-if="result.data.coRegistration" class="student-import__co-registration">
          <div
            v-for="group in result.data.coRegistration.groupsCreated"
            :key="group.name"
            class="student-import__co-registration-row"
          >
            <strong>{{ group.name }}</strong>
            <span>{{ group.memberCount }} student{{ group.memberCount === 1 ? '' : 's' }}</span>
          </div>
          <p
            v-for="(warning, index) in result.data.coRegistration.warnings"
            :key="index"
            class="student-import__warning"
          >
            {{ warning }}
          </p>
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
        class="btn btn-primary student-import__submit"
        :disabled="!canImport"
        @click="runImport"
      >
        <span v-if="importing" class="student-import__spinner" aria-hidden="true"></span>
        {{ importing ? 'Importing...' : `Import ${validRows.length || ''} student${validRows.length === 1 ? '' : 's'}` }}
      </button>
    </template>
  </FormSheet>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import FormSheet from '@/components/admin/FormSheet.vue'
import { importAdminStudents, type StudentBulkImportResult } from '@/utils/adminAPI'
import {
  parseStudentCsv,
  STUDENT_CSV_TEMPLATE,
  type ImportRowError,
  type StudentImportRow
} from '@/utils/adminStudentCsv'
import { logApiError } from '@/utils/apiError'

const PREVIEW_LIMIT = 10

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'imported', result: StudentBulkImportResult): void
}>()

const fileInput = ref<HTMLInputElement | null>(null)
const fileName = ref('')
const fileError = ref('')
const submitError = ref('')
const importing = ref(false)
const validRows = ref<StudentImportRow[]>([])
const invalidRows = ref<ImportRowError[]>([])
const result = ref<StudentBulkImportResult | null>(null)

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
    const parsed = parseStudentCsv(await file.text())
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
    STUDENT_CSV_TEMPLATE.headers.map(csvCell).join(','),
    STUDENT_CSV_TEMPLATE.sampleRow.map(csvCell).join(',')
  ].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = STUDENT_CSV_TEMPLATE.fileName
  link.click()
  URL.revokeObjectURL(url)
}

const runImport = async () => {
  if (!canImport.value) return
  importing.value = true
  submitError.value = ''
  result.value = null
  try {
    const importResult = await importAdminStudents(validRows.value)
    result.value = importResult
    emit('imported', importResult)
  } catch (importError) {
    logApiError('admin.students.csv-import', importError)
    submitError.value =
      importError instanceof Error ? importError.message : 'Students could not be imported.'
  } finally {
    importing.value = false
  }
}
</script>

<style scoped>
.student-import {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.student-import__section,
.student-import__result {
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background-color: var(--white);
  padding: 1rem;
}

.student-import__result--success {
  border-color: rgba(40, 167, 69, 0.35);
  background-color: rgba(40, 167, 69, 0.06);
}

.student-import__file-row,
.student-import__section-head,
.student-import__invalid-row,
.student-import__co-registration-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.student-import__file-row {
  margin-bottom: 0.5rem;
}

.student-import__file-row .btn,
.student-import__chips {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
}

.student-import__submit:disabled {
  opacity: 0.55;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.student-import__submit:disabled:hover {
  transform: none;
  box-shadow: none;
}

.student-import__section-head {
  margin-bottom: 0.75rem;
}

.student-import__section-head h3 {
  margin: 0;
  font-size: 1rem;
  color: var(--charcoal);
}

.student-import__section-head span,
.student-import__hint,
.student-import__summary-message,
.student-import__primary span,
.student-import__co-registration-row span {
  color: var(--text-muted);
  font-size: 0.85rem;
}

.student-import__hint {
  margin: 0.45rem 0 0;
}

.student-import__error {
  margin: 0;
  padding: 0.7rem 0.9rem;
  border-left: 4px solid var(--danger);
  border-radius: 6px;
  background-color: rgba(220, 53, 69, 0.08);
  color: var(--danger);
  font-size: 0.875rem;
}

.student-import__summary {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.student-import__badge,
.student-import__chips span {
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

.student-import__badge--ready {
  border-color: rgba(40, 167, 69, 0.35);
  background-color: rgba(40, 167, 69, 0.08);
  color: var(--success);
}

.student-import__preview-list,
.student-import__invalid-list,
.student-import__co-registration {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.student-import__preview-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 1rem;
  align-items: center;
  padding: 0.75rem;
  border-radius: 8px;
  background-color: var(--bg-light);
}

.student-import__primary {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.student-import__primary strong,
.student-import__primary span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.student-import__primary small,
.student-import__warning {
  color: #b45309;
  font-size: 0.78rem;
}

.student-import__chips {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.student-import__invalid-row {
  align-items: flex-start;
  padding: 0.6rem 0;
  border-top: 1px solid var(--border-light);
}

.student-import__invalid-row:first-child {
  border-top: none;
  padding-top: 0;
}

.student-import__invalid-row span {
  min-width: 0;
  color: var(--text-muted);
  overflow-wrap: anywhere;
}

.student-import__invalid-row strong {
  color: var(--danger);
  font-size: 0.85rem;
  text-align: right;
}

.student-import__co-registration {
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border-light);
}

.student-import__warning {
  margin: 0;
}

.student-import__spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  margin-right: 0.5rem;
  vertical-align: -2px;
  border: 2px solid rgba(255, 255, 255, 0.5);
  border-top-color: var(--white);
  border-radius: 50%;
  animation: student-import-spin 0.8s linear infinite;
}

@keyframes student-import-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 640px) {
  .student-import__file-row,
  .student-import__section-head,
  .student-import__invalid-row,
  .student-import__co-registration-row {
    align-items: flex-start;
    flex-direction: column;
    gap: 0.45rem;
  }

  .student-import__preview-row {
    grid-template-columns: 1fr;
  }

  .student-import__chips {
    justify-content: flex-start;
  }

  .student-import__invalid-row strong {
    text-align: left;
  }
}

@media (prefers-reduced-motion: reduce) {
  .student-import__spinner {
    animation: none;
  }
}
</style>
