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
          Column headers must match exactly and extra columns are ignored, so you can fill in
          the downloaded sheet and upload it back.
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
          <ul v-if="preview.checks" class="bulk-upload__checks">
            <li>
              Missing Column Header(s):
              <span :class="checkClass(!preview.checks.missing_headers.length)">
                {{ checkHeaderText }}
              </span>
            </li>
            <!-- A failed header check stops parsing, so the checks below
                 never ran — hide them rather than show a misleading None. -->
            <template v-if="!preview.checks.missing_headers.length">
              <li>
                Type:
                <span :class="checkClass(preview.checks.type_ok)">{{ checkTypeText }}</span>
              </li>
              <!-- Rows failing an earlier check skip the later validations,
                   so hide those lines rather than show a misleading None. -->
              <template v-if="preview.checks.type_ok">
                <li>
                  Incorrect group details:
                  <span :class="checkClass(!preview.checks.bad_group_rows.length)">
                    {{ checkGroupText }}
                  </span>
                </li>
                <li v-if="!preview.checks.bad_group_rows.length">
                  Incorrect mark format:
                  <span :class="checkClass(!preview.checks.bad_marks.length)">
                    {{ checkMarkText }}
                  </span>
                </li>
              </template>
            </template>
          </ul>

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

// The four preview report lines, from the parser's categorised checks.
const checkClass = (ok: boolean) => (ok ? 'bulk-upload__check--ok' : 'bulk-upload__check--bad')

const checkHeaderText = computed(() => {
  const c = preview.value?.checks
  if (!c) return ''
  return c.missing_headers.length ? c.missing_headers.join(', ') : 'None'
})

const checkTypeText = computed(() => {
  const c = preview.value?.checks
  if (!c) return ''
  return c.type_ok ? c.expected_type : `${c.found_type || 'missing'} (should be ${c.expected_type})`
})

const checkGroupText = computed(() => {
  const c = preview.value?.checks
  if (!c) return ''
  if (!c.bad_group_rows.length) return 'None'
  return c.bad_group_rows.map((g) => `row ${g.row} (${g.reason})`).join(', ')
})

const checkMarkText = computed(() => {
  const c = preview.value?.checks
  if (!c) return ''
  if (!c.bad_marks.length) return 'None'
  return c.bad_marks.map((m) => `row ${m.row} in ${m.column} (${m.hint})`).join(', ')
})

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

.bulk-upload__checks {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.85rem;
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
