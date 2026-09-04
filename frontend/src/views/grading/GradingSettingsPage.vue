<template>
  <p
    v-if="UNDER_CONSTRUCTION"
    style="background: #fff8e1; border: 1px solid #f5d97e; border-radius: 8px; color: #8a6d1a; font-size: 0.85rem; padding: 0.6rem 0.85rem; margin: 0 0 0.75rem"
  >
    <i class="fas fa-hammer" aria-hidden="true"></i>
    The backend for this page is still being built.
  </p>
  <div class="grading-settings">
    <p v-if="isLoading" class="grading-settings__hint">Loading…</p>

    <div v-else-if="loadError" class="card">
      <p class="grading-settings__load-error">Failed to load settings. {{ loadError }}</p>
      <button type="button" class="btn btn-outline btn-sm" @click="load">Try again</button>
    </div>

    <template v-else-if="settings">
      <section class="card">
        <div class="card-header">
          <h3 class="card-title">Document Setup</h3>
        </div>
        <h3 class="grading-settings__section-title">Directors</h3>
        <div class="grading-settings__fields">
          <label class="grading-settings__field">
            <span>Director 1 name</span>
            <input v-model="d1" type="text" placeholder="e.g. Prof. Alice Adams" />
          </label>
          <div class="grading-settings__field">
            <span>Director 1 signature</span>
            <div class="grading-settings__file-row">
              <button type="button" class="grading-settings__file-btn" @click="sig1Input?.click()">
                Browse…
              </button>
              <span class="grading-settings__file-name">{{ sig1?.name || baseName(settings.director_1_signature) || 'No file selected.' }}</span>
            </div>
            <p v-if="sig1" class="grading-settings__save-hint">Click Update to save signatures</p>
            <input ref="sig1Input" type="file" accept="image/*" class="grading-settings__file-input" @change="sig1 = fileOf($event)" />
            <span v-if="settings.director_1_signature" class="grading-settings__file-hint">
              Current: <code>{{ settings.director_1_signature }}</code>
            </span>
          </div>
          <label class="grading-settings__field">
            <span>Director 2 name</span>
            <input v-model="d2" type="text" placeholder="e.g. Dr. Bob Brown" />
          </label>
          <div class="grading-settings__field">
            <span>Director 2 signature</span>
            <div class="grading-settings__file-row">
              <button type="button" class="grading-settings__file-btn" @click="sig2Input?.click()">
                Browse…
              </button>
              <span class="grading-settings__file-name">{{ sig2?.name || baseName(settings.director_2_signature) || 'No file selected.' }}</span>
            </div>
            <p v-if="sig2" class="grading-settings__save-hint">Click Update to save signatures</p>
            <input ref="sig2Input" type="file" accept="image/*" class="grading-settings__file-input" @change="sig2 = fileOf($event)" />
            <span v-if="settings.director_2_signature" class="grading-settings__file-hint">
              Current: <code>{{ settings.director_2_signature }}</code>
            </span>
          </div>
        </div>
      </section>

      <section class="card">
        <h3 class="grading-settings__section-title">Docx templates</h3>
        <p class="grading-settings__note">
          Uploaded templates override the built-in fallbacks. Use the placeholders listed
          under each template; anything else is left untouched.
        </p>
        <div class="grading-settings__fields">
          <div class="grading-settings__template">
            <div class="grading-settings__field">
              <span>Marks summary template (.docx)</span>
              <div class="grading-settings__file-row">
                <button type="button" class="grading-settings__file-btn" @click="summaryInput?.click()">
                  Browse…
                </button>
                <span class="grading-settings__file-name">{{ summaryTpl?.name || baseName(settings.marks_summary_template) || 'No file selected.' }}</span>
              </div>
              <input ref="summaryInput" type="file" accept=".docx" class="grading-settings__file-input" @change="pickTemplate('marks-summary', $event)" />
              <span v-if="settings.marks_summary_template" class="grading-settings__file-hint">
                Current: <code>{{ settings.marks_summary_template }}</code>
              </span>
            </div>
            <p class="grading-settings__note">
              Expected variables (typed as text in the document) — green ones were found in
              the {{ summaryTpl ? 'selected file' : 'saved template' }}:
            </p>
            <ul class="grading-settings__tokens">
              <li v-for="chip in SUMMARY_TOKENS" :key="chip.label">
                <code :class="{ 'is-found': isFound('marks-summary', chip) }">{{ chip.label }}</code>
              </li>
            </ul>
            <p v-if="unknownIn('marks-summary').length" class="grading-settings__unknown">
              In the template but not recognised (these render blank):
              <code v-for="name in unknownIn('marks-summary')" :key="name">{{ name }}</code>
            </p>
            <button
              type="button"
              class="btn btn-outline btn-sm"
              :disabled="testing !== ''"
              @click="testRender('marks-summary')"
            >
              {{ testing === 'marks-summary' ? 'Rendering…' : 'Test' }}
            </button>
            <p v-if="summaryTpl" class="grading-settings__save-hint">
              Click Update to save templates
            </p>
          </div>

          <div class="grading-settings__template">
            <div class="grading-settings__field">
              <span>Certificate template (.docx)</span>
              <div class="grading-settings__file-row">
                <button type="button" class="grading-settings__file-btn" @click="certInput?.click()">
                  Browse…
                </button>
                <span class="grading-settings__file-name">{{ certTpl?.name || baseName(settings.certificate_template) || 'No file selected.' }}</span>
              </div>
              <input ref="certInput" type="file" accept=".docx" class="grading-settings__file-input" @change="pickTemplate('certificate', $event)" />
              <span v-if="settings.certificate_template" class="grading-settings__file-hint">
                Current: <code>{{ settings.certificate_template }}</code>
              </span>
            </div>
            <p class="grading-settings__note">
              Expected fields (Word content controls — insert via Developer tab, with the
              tag/alias set to the name below):
            </p>
            <ul class="grading-settings__tokens">
              <li v-for="chip in CERTIFICATE_FIELDS" :key="chip.label">
                <code :class="{ 'is-found': isFound('certificate', chip) }">{{ chip.label }}</code>
              </li>
            </ul>
            <p v-if="unknownIn('certificate').length" class="grading-settings__unknown">
              In the template but not recognised (these render blank):
              <code v-for="name in unknownIn('certificate')" :key="name">{{ name }}</code>
            </p>
            <button
              type="button"
              class="btn btn-outline btn-sm"
              :disabled="testing !== ''"
              @click="testRender('certificate')"
            >
              {{ testing === 'certificate' ? 'Rendering…' : 'Test' }}
            </button>
            <p v-if="certTpl" class="grading-settings__save-hint">
              Click Update to save templates
            </p>
          </div>
        </div>
      </section>

      <p v-if="actionError" class="grading-settings__banner grading-settings__banner--error">
        {{ actionError }}
      </p>
      <p v-if="savedMessage" class="grading-settings__banner grading-settings__banner--ok">
        {{ savedMessage }}
      </p>

      <div class="grading-settings__actions">
        <button
          type="button"
          class="btn btn-primary"
          :disabled="isSaving || !hasChanges"
          @click="save"
        >
          {{ isSaving ? 'Updating…' : 'Update' }}
        </button>
        <button
          type="button"
          class="btn btn-outline"
          :disabled="isSaving || !hasPickedFiles"
          @click="resetFiles"
        >
          Reset
        </button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import {
  downloadCandidateTestRender,
  downloadTemplateTestRender,
  fetchGradingSettings,
  fetchTemplateScan,
  scanTemplateCandidate,
  updateGradingSettings,
  type GradingSettingsDetail,
  type TemplateScan
} from '@/utils/gradingAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'

// Flip to false once the backend flow is signed off.
const UNDER_CONSTRUCTION = true

const settings = ref<GradingSettingsDetail | null>(null)
const isLoading = ref(false)
const loadError = ref('')
const actionError = ref('')
const savedMessage = ref('')
const isSaving = ref(false)

const d1 = ref('')
const d2 = ref('')
const sig1 = ref<File | null>(null)
const sig2 = ref<File | null>(null)
const summaryTpl = ref<File | null>(null)
const certTpl = ref<File | null>(null)

const sig1Input = ref<HTMLInputElement | null>(null)
const sig2Input = ref<HTMLInputElement | null>(null)
const summaryInput = ref<HTMLInputElement | null>(null)
const certInput = ref<HTMLInputElement | null>(null)

const fileOf = (event: Event) => (event.target as HTMLInputElement).files?.[0] ?? null

// Stored files come back as storage paths/URLs; show just the filename
// beside Browse when nothing new has been picked.
const baseName = (value: string | null | undefined) => {
  if (!value) return ''
  const last = value.split('/').pop() || ''
  try {
    return decodeURIComponent(last)
  } catch {
    return last
  }
}

const hasPickedFiles = computed(() =>
  Boolean(sig1.value || sig2.value || summaryTpl.value || certTpl.value)
)

// Update stays disabled until something actually differs from the loaded
// settings — an edited director name or a picked file.
const hasChanges = computed(() => {
  const s = settings.value
  if (!s) return false
  return (
    d1.value !== (s.director_1_name || '') ||
    d2.value !== (s.director_2_name || '') ||
    hasPickedFiles.value
  )
})

// Same unsaved-changes guard as RubricForm: leaving with pending edits or
// picked files gets a prompt first, since nothing is stored until Update.
const UNSAVED_MESSAGE = 'You have unsaved changes. Leave without updating?'

// Tab close / reload — the browser shows its own generic prompt.
const onBeforeUnload = (event: BeforeUnloadEvent) => {
  if (!hasChanges.value) return
  event.preventDefault()
  event.returnValue = ''
}
window.addEventListener('beforeunload', onBeforeUnload)
onBeforeUnmount(() => window.removeEventListener('beforeunload', onBeforeUnload))

// In-app navigation, including the other Management tabs (each is a route).
onBeforeRouteLeave(() => !hasChanges.value || window.confirm(UNSAVED_MESSAGE))

// Server-side upload checks reject per field; map the API names onto the
// labels this page shows so the error banner names the file that failed.
const FIELD_LABELS: Record<string, string> = {
  director_1_name: 'Director 1 name',
  director_2_name: 'Director 2 name',
  director_1_signature: 'Director 1 signature',
  director_2_signature: 'Director 2 signature',
  marks_summary_template: 'Marks summary template',
  certificate_template: 'Certificate template'
}


// The variables each template can reference, matching the field maps in
// backend apps/grading/services/docx.py (marks_release_fields /
// certificate_fields). Shown on the page so template authors never have to
// ask a developer which placeholders exist.
/** A chip may stand for a run of placeholders (P1…P10), so it carries every
 *  underlying name — the chip lights up when the template uses any of them. */
interface Placeholder {
  label: string
  names: string[]
}

const token = (name: string): Placeholder => ({ label: `<<[${name}]>>`, names: [name] })
const series = (prefix: string, count: number, suffix = ''): Placeholder => {
  const names = Array.from({ length: count }, (_, i) => `${prefix}${i + 1}${suffix}`)
  return { label: `<<[${names[0]}]>> … <<[${names[names.length - 1]}]>>`, names }
}

const SUMMARY_TOKENS: Placeholder[] = [
  token('TeamCode'),
  token('ProjectTitle'),
  token('ProjectCategory'),
  token('SolutionCategory'),
  token('Students'),
  token('Mentor'),
  token('Supervisors'),
  token('Schools'),
  series('P', 10),
  series('P', 10, 'Comment'),
  token('PosterComment'),
  series('S', 4),
  series('S', 4, 'Comment'),
  token('PosterTotal'),
  token('SAQTotal'),
  token('CombinedTotal'),
  token('Director1Name'),
  token('Director2Name'),
  token('Director1Signature'),
  token('Director2Signature')
]
const CERTIFICATE_FIELDS: Placeholder[] = [
  'firstName',
  'lastName',
  'projectTitle',
  'director1Name',
  'director2Name',
  'director1Signature',
  'director2Signature'
].map((name) => ({ label: name, names: [name] }))

const testing = ref<'' | 'marks-summary' | 'certificate'>('')

// What the saved template actually contains, so chips can show which
// placeholders were found and which stray ones would render blank.
const scans = ref<Record<string, TemplateScan | null>>({
  'marks-summary': null,
  certificate: null
})

const isFound = (kind: string, chip: Placeholder) => {
  const present = scans.value[kind]?.present
  return Boolean(present && chip.names.some((name) => present.includes(name)))
}

const unknownIn = (kind: string) => scans.value[kind]?.unknown ?? []

const loadScans = async () => {
  await Promise.all(
    (['marks-summary', 'certificate'] as const).map(async (kind) => {
      try {
        scans.value[kind] = await fetchTemplateScan(kind)
      } catch {
        // Best-effort: without a scan the chips simply stay uncoloured.
        scans.value[kind] = null
      }
    })
  )
}

// Picking a template file previews it: the chips recolour from a server-side
// scan of the picked file, and Test renders it — all without storing anything.
// Only Save replaces the template the real documents are generated from.
const pickTemplate = async (kind: 'marks-summary' | 'certificate', event: Event) => {
  const isSummary = kind === 'marks-summary'
  const file = fileOf(event)
  const picked = isSummary ? summaryTpl : certTpl
  picked.value = file
  actionError.value = ''
  if (!file) {
    // Selection cleared — the chips describe the saved template again.
    await loadScans()
    return
  }
  try {
    scans.value[kind] = await scanTemplateCandidate(kind, file)
  } catch (err) {
    // The renderer can't open this file; drop the pick so Save can't send it.
    picked.value = null
    const input = isSummary ? summaryInput.value : certInput.value
    if (input) input.value = ''
    const label = isSummary
      ? FIELD_LABELS.marks_summary_template
      : FIELD_LABELS.certificate_template
    actionError.value = `${label}: ${apiErrorFromUnknown(err).message}`
  }
}

const testRender = async (kind: 'marks-summary' | 'certificate') => {
  actionError.value = ''
  testing.value = kind
  const candidate = kind === 'marks-summary' ? summaryTpl.value : certTpl.value
  try {
    // A picked file is test-driven as-is; otherwise the saved template runs.
    if (candidate) await downloadCandidateTestRender(kind, candidate)
    else await downloadTemplateTestRender(kind)
  } catch (err) {
    actionError.value = apiErrorFromUnknown(err).message
  } finally {
    testing.value = ''
  }
}

const load = async () => {
  isLoading.value = true
  loadError.value = ''
  try {
    settings.value = await fetchGradingSettings()
    d1.value = settings.value.director_1_name || ''
    d2.value = settings.value.director_2_name || ''
  } catch (err) {
    settings.value = null
    loadError.value = apiErrorFromUnknown(err).message
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  void load()
  void loadScans()
})

const clearFilePickers = () => {
  sig1.value = null
  sig2.value = null
  summaryTpl.value = null
  certTpl.value = null
  for (const input of [sig1Input.value, sig2Input.value, summaryInput.value, certInput.value]) {
    if (input) input.value = ''
  }
}

// Drop every picked-but-not-saved file and describe the saved templates
// again; director name edits are left alone.
const resetFiles = async () => {
  clearFilePickers()
  actionError.value = ''
  savedMessage.value = ''
  await loadScans()
}

// Name-only edits go as JSON; any file present switches the whole PATCH to
// multipart (the API accepts both on the same endpoint).
const save = async () => {
  actionError.value = ''
  savedMessage.value = ''
  isSaving.value = true
  try {
    const hasFile = sig1.value || sig2.value || summaryTpl.value || certTpl.value
    let body: FormData | { director_1_name: string; director_2_name: string }
    if (hasFile) {
      const fd = new FormData()
      fd.append('director_1_name', d1.value)
      fd.append('director_2_name', d2.value)
      if (sig1.value) fd.append('director_1_signature', sig1.value)
      if (sig2.value) fd.append('director_2_signature', sig2.value)
      if (summaryTpl.value) fd.append('marks_summary_template', summaryTpl.value)
      if (certTpl.value) fd.append('certificate_template', certTpl.value)
      body = fd
    } else {
      body = { director_1_name: d1.value, director_2_name: d2.value }
    }
    settings.value = await updateGradingSettings(body)
    d1.value = settings.value.director_1_name || ''
    d2.value = settings.value.director_2_name || ''
    clearFilePickers()
    savedMessage.value = 'Settings updated.'
    // A newly uploaded template changes which placeholders are present.
    await loadScans()
  } catch (err) {
    const apiError = apiErrorFromUnknown(err)
    // A rejected upload 400s the whole PATCH with per-field messages — name
    // the file that failed so the admin knows nothing was replaced.
    const fieldErrors = Object.entries(apiError.fields ?? {}).map(
      ([field, messages]) => `${FIELD_LABELS[field] ?? field}: ${messages.join(' ')}`
    )
    actionError.value = fieldErrors.length ? fieldErrors.join(' ') : apiError.message
  } finally {
    isSaving.value = false
  }
}
</script>

<style scoped>
.grading-settings {
  max-width: 42rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  /* Room to scroll past the Update button instead of it hugging the fold. */
  padding-bottom: 2rem;
}


.grading-settings__hint {
  color: var(--text-muted);
  font-size: 0.9rem;
}

.grading-settings__load-error {
  color: var(--danger);
  margin-bottom: 0.5rem;
}

.grading-settings__section-title {
  font-size: 1.05rem;
  margin-bottom: 0.75rem;
}

.grading-settings__note {
  color: var(--text-muted);
  font-size: 0.82rem;
  margin-bottom: 0.75rem;
}

.grading-settings__note code {
  background: var(--bg-light);
  border-radius: 4px;
  padding: 0.05rem 0.3rem;
}

.grading-settings__fields {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.grading-settings__template {
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 0.85rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.grading-settings__template .grading-settings__note {
  margin-bottom: 0;
}

/* Template captions: black but normal weight, per design feedback. */
.grading-settings__template .grading-settings__field > span {
  color: #000;
  font-weight: 400;
}

/* Breathing room between the caption and its Browse row. */
.grading-settings__template .grading-settings__field > span:first-child {
  margin-bottom: 1rem;
}

/* Match the restyled file-picker buttons above. */
.grading-settings__template .btn {
  align-self: flex-start;
  background-color: transparent;
  color: var(--dark-green);
  border: 1px solid var(--border-light);
  border-radius: 4px;
  padding: 0.3rem 0.7rem;
  font-size: 0.84rem;
  font-weight: 500;
}

.grading-settings__template .btn:hover:not(:disabled) {
  background-color: var(--light-green);
  border-color: var(--dark-green);
}

.grading-settings__tokens {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.grading-settings__tokens code {
  display: inline-block;
  background: var(--bg-light);
  border: 1px solid var(--border-light);
  border-radius: 4px;
  padding: 0.1rem 0.4rem;
  font-size: 0.78rem;
  white-space: nowrap;
}

/* Found in the saved template — the rest are simply unused. */
.grading-settings__tokens code.is-found {
  background: var(--accent-green-soft);
  border-color: var(--dark-green);
  color: var(--dark-green);
}

.grading-settings__unknown {
  color: #b45309;
  font-size: 0.82rem;
  margin: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
}

.grading-settings__unknown code {
  background: color-mix(in srgb, #b45309 10%, transparent);
  border: 1px solid color-mix(in srgb, #b45309 35%, transparent);
  border-radius: 4px;
  padding: 0.1rem 0.4rem;
  font-size: 0.78rem;
  white-space: nowrap;
}

/* Yellow nudge under Test while a picked file is still unsaved. */
.grading-settings__save-hint {
  color: #b8860b;
  font-size: 0.85rem;
  margin: 0;
}

.grading-settings__actions {
  display: flex;
  gap: 0.6rem;
}

/* Between .btn-sm and the full-size .btn — the page's main actions deserve
   slightly more presence than the outline Test buttons. */
.grading-settings__actions .btn {
  padding: 0.5rem 1.1rem;
  font-size: 0.92rem;
}


.grading-settings__field {
  display: grid;
  gap: 0.3rem;
  font-size: 0.9rem;
}

.grading-settings__field > span {
  color: var(--text-muted);
}

.grading-settings__field input[type='text'] {
  border: 1px solid var(--border-light);
  border-radius: 6px;
  padding: 0.45rem 0.6rem;
  font-size: 0.9rem;
  font-family: inherit;
  background: var(--surface-elevated);
  color: var(--charcoal);
}

.grading-settings__field input[type='text']:focus {
  outline: none;
  border-color: var(--dark-green);
}

/* Custom file pickers: the native input is hidden because its "No file
   selected" text is part of the same clickable control — only our button
   should open the dialog. Styled to match the app's outline buttons. */
.grading-settings__file-input {
  display: none;
}

.grading-settings__file-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.grading-settings__file-btn {
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

.grading-settings__file-btn:hover {
  background-color: var(--light-green);
  border-color: var(--dark-green);
}

.grading-settings__file-name {
  color: var(--text-muted);
  font-size: 0.85rem;
}

.grading-settings__file-hint {
  color: var(--text-muted);
  font-size: 0.78rem;
  word-break: break-all;
}

.grading-settings__file-hint code {
  background: var(--bg-light);
  border-radius: 4px;
  padding: 0.05rem 0.3rem;
}

.grading-settings__banner {
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  margin: 0;
}

.grading-settings__banner--error {
  background: color-mix(in srgb, var(--danger) 12%, transparent);
  color: var(--danger);
}

.grading-settings__banner--ok {
  background: var(--accent-green-soft);
  color: var(--dark-green);
}
</style>
