<template>
  <div class="grading-settings">
    <p v-if="isLoading" class="grading-settings__hint">Loading…</p>

    <div v-else-if="loadError" class="card">
      <p class="grading-settings__load-error">Failed to load settings. {{ loadError }}</p>
      <button type="button" class="btn btn-outline btn-sm" @click="load">Try again</button>
    </div>

    <template v-else-if="settings">
      <section class="card">
        <h3 class="grading-settings__section-title">Directors</h3>
        <div class="grading-settings__fields">
          <label class="grading-settings__field">
            <span>Director 1 name</span>
            <input v-model="d1" type="text" placeholder="e.g. Prof. Alice Adams" />
          </label>
          <label class="grading-settings__field">
            <span>Director 1 signature</span>
            <input ref="sig1Input" type="file" accept="image/*" @change="sig1 = fileOf($event)" />
            <span v-if="settings.director_1_signature" class="grading-settings__file-hint">
              Current: <code>{{ settings.director_1_signature }}</code>
            </span>
          </label>
          <label class="grading-settings__field">
            <span>Director 2 name</span>
            <input v-model="d2" type="text" placeholder="e.g. Dr. Bob Brown" />
          </label>
          <label class="grading-settings__field">
            <span>Director 2 signature</span>
            <input ref="sig2Input" type="file" accept="image/*" @change="sig2 = fileOf($event)" />
            <span v-if="settings.director_2_signature" class="grading-settings__file-hint">
              Current: <code>{{ settings.director_2_signature }}</code>
            </span>
          </label>
        </div>
      </section>

      <section class="card">
        <h3 class="grading-settings__section-title">Docx templates</h3>
        <p class="grading-settings__note">
          Uploaded templates override the built-in fallbacks. Use Jinja-style
          <code>{{ TPL_MARKER_EXAMPLE }}</code> markers. See docx.py for the expected context keys.
        </p>
        <div class="grading-settings__fields">
          <label class="grading-settings__field">
            <span>Marks summary template (.docx)</span>
            <input ref="summaryInput" type="file" accept=".docx" @change="summaryTpl = fileOf($event)" />
            <span v-if="settings.marks_summary_template" class="grading-settings__file-hint">
              Current: <code>{{ settings.marks_summary_template }}</code>
            </span>
          </label>
          <label class="grading-settings__field">
            <span>Certificate template (.docx)</span>
            <input ref="certInput" type="file" accept=".docx" @change="certTpl = fileOf($event)" />
            <span v-if="settings.certificate_template" class="grading-settings__file-hint">
              Current: <code>{{ settings.certificate_template }}</code>
            </span>
          </label>
        </div>
      </section>

      <p v-if="actionError" class="grading-settings__banner grading-settings__banner--error">
        {{ actionError }}
      </p>
      <p v-if="savedMessage" class="grading-settings__banner grading-settings__banner--ok">
        {{ savedMessage }}
      </p>

      <div>
        <button type="button" class="btn btn-primary btn-sm" :disabled="isSaving" @click="save">
          {{ isSaving ? 'Saving…' : 'Save' }}
        </button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import {
  fetchGradingSettings,
  updateGradingSettings,
  type GradingSettingsDetail
} from '@/utils/gradingAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'

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

// Literal Jinja marker for the help text — kept in script because "{{" inside
// a template text node would be parsed as a Vue interpolation.
const TPL_MARKER_EXAMPLE = '{' + '{ variable }' + '}'

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

onMounted(load)

const clearFilePickers = () => {
  sig1.value = null
  sig2.value = null
  summaryTpl.value = null
  certTpl.value = null
  for (const input of [sig1Input.value, sig2Input.value, summaryInput.value, certInput.value]) {
    if (input) input.value = ''
  }
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
    savedMessage.value = 'Settings saved.'
  } catch (err) {
    actionError.value = apiErrorFromUnknown(err).message
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
