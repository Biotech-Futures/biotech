<template>
  <button type="button" class="btn btn-outline btn-sm" @click="openDialog">
    <i class="fas fa-upload" aria-hidden="true"></i> Upload marks
  </button>

  <Teleport to="body">
    <div v-if="open" class="bulk-upload__overlay" @click.self="closeDialog">
      <div class="bulk-upload__dialog" role="dialog" aria-modal="true" aria-label="Upload marks">
        <div class="bulk-upload__head">
          <h3 class="bulk-upload__title">Upload marks for {{ typeLabel }}</h3>
          <button
            type="button"
            class="bulk-upload__close"
            aria-label="Close"
            @click="closeDialog"
          >
            &times;
          </button>
        </div>

        <p class="bulk-upload__desc">
          XLSX or CSV in the export's shape (one row per group)<br />
          <code>group_id</code>, <code>group_name</code>, <code>type</code>,<br />
          Then <code>r1_mark</code>/<code>r1_comment</code> per criterion<template
            v-if="code !== 'SAQ'"
          >, and <code>overall_comment</code></template>
        </p>
        <p class="bulk-upload__desc">
          Value of <code>type</code> is <code>{{ typeLabel }}</code> for all rows<br />
          Extra columns are ignored, so you can fill in the downloaded sheet and upload it back.
        </p>

        <div class="bulk-upload__file-row">
          <button type="button" class="bulk-upload__file-btn" @click="fileInput?.click()">
            Browse…
          </button>
          <span class="bulk-upload__file-name">{{ file?.name || 'No file selected.' }}</span>
        </div>
        <input
          ref="fileInput"
          type="file"
          accept=".xlsx,.csv"
          class="bulk-upload__file"
          @change="onFileChange"
        />

        <p v-if="requestError" class="bulk-upload__request-error">{{ requestError }}</p>

        <div v-if="preview" class="bulk-upload__preview">
          <div class="bulk-upload__badges">
            <span class="bulk-upload__badge bulk-upload__badge--creates">
              creates <strong>{{ preview.summary.creates }}</strong>
            </span>
            <span class="bulk-upload__badge bulk-upload__badge--updates">
              updates <strong>{{ preview.summary.updates }}</strong>
            </span>
            <span class="bulk-upload__badge bulk-upload__badge--muted">
              unchanged <strong>{{ preview.summary.unchanged }}</strong>
            </span>
            <span
              class="bulk-upload__badge"
              :class="preview.summary.errors > 0 ? 'bulk-upload__badge--errors' : 'bulk-upload__badge--muted'"
            >
              errors <strong>{{ preview.summary.errors }}</strong>
            </span>
          </div>

          <div v-if="preview.errors.length" class="bulk-upload__errors">
            <table>
              <thead>
                <tr>
                  <th class="bulk-upload__row-col">Row</th>
                  <th>Error</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(e, i) in preview.errors" :key="i">
                  <td class="bulk-upload__row-col">{{ e.row }}</td>
                  <td>{{ e.message }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <p v-if="preview.summary.errors > 0" class="bulk-upload__fix-hint">
            Fix the errors and re-upload before applying.
          </p>
        </div>

        <div class="bulk-upload__footer">
          <button
            type="button"
            class="btn btn-outline btn-sm"
            :disabled="!file || busy !== 'idle'"
            @click="doPreview"
          >
            {{ busy === 'preview' ? 'Previewing…' : 'Preview' }}
          </button>
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
import { bulkUploadMarks, type BulkUploadResponse } from '@/utils/gradingAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'

// Two-step flow:
//   1. Pick a file → dry_run=true → diff summary + errors table.
//   2. If no errors, "Apply" → dry_run=false → emit + close.
// Single dialog rather than a wizard: fewer clicks, admin can swap the file
// and re-preview in place. The backend re-parses on apply so the committed
// diff reflects current DB state, not just what was previewed.
const props = defineProps<{ code: string }>()

// Friendly type labels, matching the sheet's `type` column values.
const TYPE_LABELS: Record<string, string> = {
  SAQ: 'SAQs',
  POSTER: 'Poster',
  REPORT: 'Report',
  PROTOTYPE: 'Prototype'
}
const typeLabel = computed(() => TYPE_LABELS[props.code] ?? props.code)

const emit = defineEmits<{
  applied: [written: number]
}>()

const open = ref(false)
const file = ref<File | null>(null)
const preview = ref<BulkUploadResponse | null>(null)
const requestError = ref('')
const busy = ref<'idle' | 'preview' | 'apply'>('idle')
const fileInput = ref<HTMLInputElement | null>(null)

const reset = () => {
  file.value = null
  preview.value = null
  requestError.value = ''
  busy.value = 'idle'
  // Clear the hidden native input too, so picking the same file again
  // still fires a change event.
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
  preview.value = null
  requestError.value = ''
}

const doPreview = async () => {
  if (!file.value) return
  busy.value = 'preview'
  requestError.value = ''
  preview.value = null
  try {
    preview.value = await bulkUploadMarks(props.code, file.value, true)
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
    const data = await bulkUploadMarks(props.code, file.value, false)
    busy.value = 'idle'
    open.value = false
    emit('applied', data.written ?? 0)
    reset()
  } catch (err) {
    busy.value = 'idle'
    requestError.value = `Apply failed: ${apiErrorFromUnknown(err).message}`
  }
}
</script>

<style scoped>
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
  color: var(--charcoal);
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
  color: var(--charcoal);
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

/* Custom file picker matching the Document Setup page: the native input is
   hidden because its "No file selected" text is part of the same clickable
   control — only our button should open the dialog. */
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

.bulk-upload__preview {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.bulk-upload__badges {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.bulk-upload__badge {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  border-radius: 6px;
  padding: 0.15rem 0.55rem;
  font-size: 0.8rem;
}

.bulk-upload__badge--creates {
  background: var(--accent-green-soft);
  color: var(--dark-green);
}

.bulk-upload__badge--updates {
  background: color-mix(in srgb, var(--warning) 22%, transparent);
  color: #8a6100;
}

.bulk-upload__badge--errors {
  background: color-mix(in srgb, var(--danger) 14%, transparent);
  color: var(--danger);
}

.bulk-upload__badge--muted {
  background: var(--bg-light);
  color: var(--text-muted);
}

.bulk-upload__errors {
  max-height: 12rem;
  overflow: auto;
  border: 1px solid var(--border-light);
  border-radius: 8px;
}

.bulk-upload__errors table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.bulk-upload__errors th,
.bulk-upload__errors td {
  text-align: left;
  padding: 0.45rem 0.6rem;
  border-bottom: 1px solid var(--border-light);
}

.bulk-upload__errors thead th {
  background: var(--bg-light);
  color: var(--text-muted);
  font-weight: 600;
  position: sticky;
  top: 0;
}

.bulk-upload__errors tbody tr:last-child td {
  border-bottom: none;
}

.bulk-upload__row-col {
  width: 5rem;
  font-family: monospace;
}

.bulk-upload__fix-hint {
  color: var(--danger);
  font-size: 0.8rem;
  margin: 0;
}

.bulk-upload__footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}
</style>
