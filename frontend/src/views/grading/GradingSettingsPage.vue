<template>
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
            <span>Director 1 Name</span>
            <input v-model="d1" type="text" placeholder="e.g. Prof. Alice Adams" />
          </label>
          <label class="grading-settings__field">
            <span>Director 1 Position</span>
            <input v-model="p1" type="text" placeholder="e.g. Chair" />
          </label>
          <div class="grading-settings__field">
            <span>Director 1 Signature</span>
            <div class="grading-settings__file-row">
              <button type="button" class="grading-settings__file-btn" @click="sig1Input?.click()">
                Browse…
              </button>
              <span class="grading-settings__file-name">{{ sig1?.name || baseName(settings.director_1_signature) || 'No file selected.' }}</span>
            </div>
            <p
              v-if="director1Changed"
              class="grading-settings__save-hint grading-settings__save-hint--director"
            >
              Click Update to save details
            </p>
            <input ref="sig1Input" type="file" accept="image/*" class="grading-settings__file-input" @change="sig1 = fileOf($event)" />
          </div>
          <label class="grading-settings__field">
            <span>Director 2 Name</span>
            <input v-model="d2" type="text" placeholder="e.g. Dr. Bob Brown" />
          </label>
          <label class="grading-settings__field">
            <span>Director 2 Position</span>
            <input v-model="p2" type="text" placeholder="e.g. Co-Chair" />
          </label>
          <div class="grading-settings__field">
            <span>Director 2 Signature</span>
            <div class="grading-settings__file-row">
              <button type="button" class="grading-settings__file-btn" @click="sig2Input?.click()">
                Browse…
              </button>
              <span class="grading-settings__file-name">{{ sig2?.name || baseName(settings.director_2_signature) || 'No file selected.' }}</span>
            </div>
            <p
              v-if="director2Changed"
              class="grading-settings__save-hint grading-settings__save-hint--director"
            >
              Click Update to save details
            </p>
            <input ref="sig2Input" type="file" accept="image/*" class="grading-settings__file-input" @change="sig2 = fileOf($event)" />
          </div>
        </div>
      </section>

      <section class="card">
        <h3 class="grading-settings__section-title">Docx templates</h3>
        <p class="grading-settings__note">
          Use the placeholders listed under each template. Type them as text in the template.
          Anything else is left untouched.
        </p>
        <div class="grading-settings__fields">
          <div class="grading-settings__template">
            <div class="grading-settings__field">
              <span>Marks summary template (.docx)</span>
              <button
                type="button"
                class="btn btn-outline btn-sm grading-settings__download"
                :disabled="downloading !== '' || !settings.marks_summary_template"
                @click="downloadCurrent('marks-summary')"
              >
                {{ downloading === 'marks-summary' ? 'Downloading…' : 'Download Current Template' }}
              </button>
              <div class="grading-settings__file-row">
                <button type="button" class="grading-settings__file-btn" @click="summaryInput?.click()">
                  Browse…
                </button>
                <span class="grading-settings__file-name">{{ summaryTpl?.name || baseName(settings.marks_summary_template) || 'No file selected.' }}</span>
              </div>
              <input ref="summaryInput" type="file" accept=".docx" class="grading-settings__file-input" @change="pickTemplate('marks-summary', $event)" />
            </div>
            <p class="grading-settings__note">
              Expected variables:<br />
              <span class="grading-settings__found-hint">Highlighted ones are found in the selected file:</span>
            </p>
            <ul
              v-for="(group, index) in SUMMARY_GROUPS"
              :key="index"
              class="grading-settings__tokens"
            >
              <li v-for="chip in group" :key="chip.label">
                <code :class="{ 'is-found': isFound('marks-summary', chip) }">{{ chip.label }}</code>
              </li>
            </ul>
            <p v-if="unknownIn('marks-summary').length" class="grading-settings__unknown">
              Variables present in the selected file but not recognised (these render blank):
              <code v-for="name in unknownIn('marks-summary')" :key="name">{{ name }}</code>
            </p>
            <!-- Test fills in made-up details; Test Student a real student's. -->
            <div class="grading-settings__test-row">
              <button
                type="button"
                class="btn btn-outline btn-sm"
                :disabled="testing !== '' || !(summaryTpl || settings.marks_summary_template)"
                @click="testRender('marks-summary')"
              >
                {{ testing === 'marks-summary' ? 'Rendering…' : 'Test' }}
              </button>
              <div class="grading-settings__person-test">
                <button
                  type="button"
                  class="btn btn-outline btn-sm"
                  :disabled="testing !== '' || !person['marks-summary'] || !(summaryTpl || settings.marks_summary_template)"
                  @click="testRender('marks-summary', true)"
                >
                  {{ testing === 'marks-summary-person' ? 'Rendering…' : 'Test Student' }}
                </button>
                <select
                  v-model="person['marks-summary']"
                  class="grading-settings__person-select"
                  aria-label="Student"
                  :disabled="!people['marks-summary'].length"
                >
                  <option v-if="!people['marks-summary'].length" value="">Nobody yet</option>
                  <option v-for="option in people['marks-summary']" :key="option.value" :value="option.value">
                    {{ option.label }}
                  </option>
                </select>
              </div>
            </div>
            <p v-if="summaryTpl" class="grading-settings__save-hint">
              Click Update to save templates
            </p>
          </div>

          <div class="grading-settings__template">
            <div class="grading-settings__field">
              <span>Student Certificate template (.docx)</span>
              <button
                type="button"
                class="btn btn-outline btn-sm grading-settings__download"
                :disabled="downloading !== '' || !settings.certificate_template"
                @click="downloadCurrent('certificate')"
              >
                {{ downloading === 'certificate' ? 'Downloading…' : 'Download Current Template' }}
              </button>
              <div class="grading-settings__file-row">
                <button type="button" class="grading-settings__file-btn" @click="certInput?.click()">
                  Browse…
                </button>
                <span class="grading-settings__file-name">{{ certTpl?.name || baseName(settings.certificate_template) || 'No file selected.' }}</span>
              </div>
              <input ref="certInput" type="file" accept=".docx" class="grading-settings__file-input" @change="pickTemplate('certificate', $event)" />
            </div>
            <p class="grading-settings__note">
              Expected variables:<br />
              <span class="grading-settings__found-hint">Highlighted ones are found in the selected file:</span>
            </p>
            <ul class="grading-settings__tokens">
              <li v-for="chip in CERTIFICATE_FIELDS" :key="chip.label">
                <code :class="{ 'is-found': isFound('certificate', chip) }">{{ chip.label }}</code>
              </li>
            </ul>
            <p v-if="unknownIn('certificate').length" class="grading-settings__unknown">
              Variables present in the selected file but not recognised (these render blank):
              <code v-for="name in unknownIn('certificate')" :key="name">{{ name }}</code>
            </p>
            <!-- Test fills in made-up details; Test Student a real student's. -->
            <div class="grading-settings__test-row">
              <button
                type="button"
                class="btn btn-outline btn-sm"
                :disabled="testing !== '' || !(certTpl || settings.certificate_template)"
                @click="testRender('certificate')"
              >
                {{ testing === 'certificate' ? 'Rendering…' : 'Test' }}
              </button>
              <div class="grading-settings__person-test">
                <button
                  type="button"
                  class="btn btn-outline btn-sm"
                  :disabled="testing !== '' || !person['certificate'] || !(certTpl || settings.certificate_template)"
                  @click="testRender('certificate', true)"
                >
                  {{ testing === 'certificate-person' ? 'Rendering…' : 'Test Student' }}
                </button>
                <select
                  v-model="person['certificate']"
                  class="grading-settings__person-select"
                  aria-label="Student"
                  :disabled="!people['certificate'].length"
                >
                  <option v-if="!people['certificate'].length" value="">Nobody yet</option>
                  <option v-for="option in people['certificate']" :key="option.value" :value="option.value">
                    {{ option.label }}
                  </option>
                </select>
              </div>
            </div>
            <p v-if="certTpl" class="grading-settings__save-hint">
              Click Update to save templates
            </p>
          </div>

          <div class="grading-settings__template">
            <div class="grading-settings__field">
              <span>Mentor Certificate template (.docx)</span>
              <button
                type="button"
                class="btn btn-outline btn-sm grading-settings__download"
                :disabled="downloading !== '' || !settings.mentor_certificate_template"
                @click="downloadCurrent('mentor-certificate')"
              >
                {{ downloading === 'mentor-certificate' ? 'Downloading…' : 'Download Current Template' }}
              </button>
              <div class="grading-settings__file-row">
                <button type="button" class="grading-settings__file-btn" @click="mentorInput?.click()">
                  Browse…
                </button>
                <span class="grading-settings__file-name">{{ mentorTpl?.name || baseName(settings.mentor_certificate_template) || 'No file selected.' }}</span>
              </div>
              <input ref="mentorInput" type="file" accept=".docx" class="grading-settings__file-input" @change="pickTemplate('mentor-certificate', $event)" />
            </div>
            <p class="grading-settings__note">
              Expected variables:<br />
              <span class="grading-settings__found-hint">Highlighted ones are found in the selected file:</span>
            </p>
            <ul class="grading-settings__tokens">
              <li v-for="chip in MENTOR_CERTIFICATE_FIELDS" :key="chip.label">
                <code :class="{ 'is-found': isFound('mentor-certificate', chip) }">{{ chip.label }}</code>
              </li>
            </ul>
            <p v-if="unknownIn('mentor-certificate').length" class="grading-settings__unknown">
              Variables present in the selected file but not recognised (these render blank):
              <code v-for="name in unknownIn('mentor-certificate')" :key="name">{{ name }}</code>
            </p>
            <!-- Test fills in made-up details; Test Mentor a real mentor's. -->
            <div class="grading-settings__test-row">
              <button
                type="button"
                class="btn btn-outline btn-sm"
                :disabled="testing !== '' || !(mentorTpl || settings.mentor_certificate_template)"
                @click="testRender('mentor-certificate')"
              >
                {{ testing === 'mentor-certificate' ? 'Rendering…' : 'Test' }}
              </button>
              <div class="grading-settings__person-test">
                <button
                  type="button"
                  class="btn btn-outline btn-sm"
                  :disabled="testing !== '' || !person['mentor-certificate'] || !(mentorTpl || settings.mentor_certificate_template)"
                  @click="testRender('mentor-certificate', true)"
                >
                  {{ testing === 'mentor-certificate-person' ? 'Rendering…' : 'Test Mentor' }}
                </button>
                <select
                  v-model="person['mentor-certificate']"
                  class="grading-settings__person-select"
                  aria-label="Mentor"
                  :disabled="!people['mentor-certificate'].length"
                >
                  <option v-if="!people['mentor-certificate'].length" value="">Nobody yet</option>
                  <option v-for="option in people['mentor-certificate']" :key="option.value" :value="option.value">
                    {{ option.label }}
                  </option>
                </select>
              </div>
            </div>
            <p v-if="mentorTpl" class="grading-settings__save-hint">
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
import { computed, onBeforeUnmount, onMounted, ref, type Ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { useFlashMessage } from '@/composables/useFlashMessage'
import {
  downloadCandidateTestRender,
  downloadSavedTemplate,
  downloadTemplateTestRender,
  fetchGradingSettings,
  fetchTemplateScan,
  fetchTemplateTestPeople,
  scanTemplateCandidate,
  updateGradingSettings,
  type GradingSettingsDetail,
  type TemplateKind,
  type TemplateScan,
  type TestEmailRecipient
} from '@/utils/gradingAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'

const settings = ref<GradingSettingsDetail | null>(null)
const isLoading = ref(false)
const loadError = ref('')
const actionError = ref('')
const { message: savedMessage, show: flashSaved } = useFlashMessage()
const isSaving = ref(false)

const d1 = ref('')
const d2 = ref('')
const p1 = ref('')
const p2 = ref('')
const sig1 = ref<File | null>(null)
const sig2 = ref<File | null>(null)
const summaryTpl = ref<File | null>(null)
const certTpl = ref<File | null>(null)
const mentorTpl = ref<File | null>(null)

const sig1Input = ref<HTMLInputElement | null>(null)
const sig2Input = ref<HTMLInputElement | null>(null)
const summaryInput = ref<HTMLInputElement | null>(null)
const certInput = ref<HTMLInputElement | null>(null)
const mentorInput = ref<HTMLInputElement | null>(null)

// Each template's picked file, its Browse input and its settings field.
const PICKED: Record<TemplateKind, Ref<File | null>> = {
  'marks-summary': summaryTpl,
  certificate: certTpl,
  'mentor-certificate': mentorTpl
}
const INPUTS: Record<TemplateKind, Ref<HTMLInputElement | null>> = {
  'marks-summary': summaryInput,
  certificate: certInput,
  'mentor-certificate': mentorInput
}
const TEMPLATE_FIELD: Record<TemplateKind, string> = {
  'marks-summary': 'marks_summary_template',
  certificate: 'certificate_template',
  'mentor-certificate': 'mentor_certificate_template'
}

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
  Boolean(sig1.value || sig2.value || summaryTpl.value || certTpl.value || mentorTpl.value)
)

// Each director's details differ from what is saved: an edited name or
// position, or a picked signature. Drives that director's save hint.
const director1Changed = computed(() => {
  const s = settings.value
  if (!s) return false
  return (
    d1.value !== (s.director_1_name || '') ||
    p1.value !== (s.director_1_position || '') ||
    Boolean(sig1.value)
  )
})
const director2Changed = computed(() => {
  const s = settings.value
  if (!s) return false
  return (
    d2.value !== (s.director_2_name || '') ||
    p2.value !== (s.director_2_position || '') ||
    Boolean(sig2.value)
  )
})

// Update stays disabled until something actually differs from the loaded
// settings — an edited director detail or a picked file.
const hasChanges = computed(
  () => director1Changed.value || director2Changed.value || hasPickedFiles.value
)

// The text fields as the form currently holds them, for either save body.
const directorText = () => ({
  director_1_name: d1.value,
  director_1_position: p1.value,
  director_2_name: d2.value,
  director_2_position: p2.value
})

const showStoredText = (s: GradingSettingsDetail) => {
  d1.value = s.director_1_name || ''
  d2.value = s.director_2_name || ''
  p1.value = s.director_1_position || ''
  p2.value = s.director_2_position || ''
}

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
  director_1_name: 'Director 1 Name',
  director_1_position: 'Director 1 Position',
  director_2_name: 'Director 2 Name',
  director_2_position: 'Director 2 Position',
  director_1_signature: 'Director 1 Signature',
  director_2_signature: 'Director 2 Signature',
  marks_summary_template: 'Marks summary template',
  certificate_template: 'Student Certificate template',
  mentor_certificate_template: 'Mentor Certificate template'
}


// The variables each template can reference, matching the field maps in
// backend apps/grading/services/docx.py (marks_release_fields /
// certificate_fields / mentor_certificate_fields). Shown on the page so template authors never have to
// ask a developer which placeholders exist.
/** A chip may stand for a run of placeholders (P1…P10), so it carries every
 *  underlying name — the chip lights up when the template uses any of them. */
interface Placeholder {
  label: string
  names: string[]
}

const token = (name: string): Placeholder => ({ label: `{{${name}}}`, names: [name] })
const series = (prefix: string, count: number, suffix = ''): Placeholder => {
  const names = Array.from({ length: count }, (_, i) => `${prefix}${i + 1}${suffix}`)
  return { label: `{{${names[0]}}} … {{${names[names.length - 1]}}}`, names }
}

// Team details, then marks and comments, then totals and directors. Each
// group is its own list, so the space between groups matches the space
// between the other parts of the template card.
const SUMMARY_GROUPS: Placeholder[][] = [
  [
    token('Year'),
    token('TeamCode'),
    token('ProjectTitle'),
    token('ProjectCategoryHeading'),
    token('ProjectCategory'),
    token('SolutionCategory'),
    token('Students'),
    token('Mentor'),
    token('SupervisorHeading'),
    token('Supervisors'),
    token('SchoolHeading'),
    token('Schools')
  ],
  [
    series('PosterRubric', 10),
    series('PM', 10),
    series('PosterComment', 10),
    token('PosterOverallComment'),
    series('ShortAnswerQuestionRubric', 4),
    series('SM', 4),
    series('ShortAnswerQuestionComment', 4),
    token('ShortAnswerQuestionOverallComment')
  ],
  [
    token('PMTotal'),
    token('SMTotal'),
    token('CombinedTotal'),
    token('Director1Signature'),
    token('Director2Signature'),
    token('Director1Name'),
    token('Director2Name'),
    token('Director1Position'),
    token('Director2Position')
  ]
]
const CERTIFICATE_FIELDS: Placeholder[] = [
  'Year',
  'Name',
  'ProjectTitle',
  'Date',
  'Director1Signature',
  'Director2Signature',
  'Director1Name',
  'Director2Name',
  'Director1Position',
  'Director2Position'
].map(token)
// The same variables as the student certificate.
const MENTOR_CERTIFICATE_FIELDS: Placeholder[] = [
  'Year',
  'Name',
  'ProjectTitle',
  'Date',
  'Director1Signature',
  'Director2Signature',
  'Director1Name',
  'Director2Name',
  'Director1Position',
  'Director2Position'
].map(token)

// Which Test is rendering: a kind, or "<kind>-person" for its Test Student
// or Test Mentor.
const testing = ref<'' | TemplateKind | `${TemplateKind}-person`>('')

// What the saved template actually contains, so chips can show which
// placeholders were found and which stray ones would render blank.
const scans = ref<Record<string, TemplateScan | null>>({
  'marks-summary': null,
  certificate: null,
  'mentor-certificate': null
})

const isFound = (kind: string, chip: Placeholder) => {
  const present = scans.value[kind]?.present
  return Boolean(present && chip.names.some((name) => present.includes(name)))
}

const unknownIn = (kind: string) => scans.value[kind]?.unknown ?? []

const loadScans = async () => {
  await Promise.all(
    (['marks-summary', 'certificate', 'mentor-certificate'] as const).map(async (kind) => {
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
const pickTemplate = async (kind: TemplateKind, event: Event) => {
  const file = fileOf(event)
  const picked = PICKED[kind]
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
    const input = INPUTS[kind].value
    if (input) input.value = ''
    actionError.value = `${FIELD_LABELS[TEMPLATE_FIELD[kind]]}: ${apiErrorFromUnknown(err).message}`
  }
}

// The saved template as uploaded, to edit and upload back. A file picked but
// not yet saved isn't it, so the button always fetches the saved one.
const downloading = ref<'' | TemplateKind>('')

const downloadCurrent = async (kind: TemplateKind) => {
  actionError.value = ''
  downloading.value = kind
  try {
    await downloadSavedTemplate(kind)
  } catch (err) {
    actionError.value = apiErrorFromUnknown(err).message
  } finally {
    downloading.value = ''
  }
}

// Who each template can be tested with: this year's students, or mentors for
// the mentor certificate. The first is picked to start with.
const people = ref<Record<TemplateKind, TestEmailRecipient[]>>({
  'marks-summary': [],
  certificate: [],
  'mentor-certificate': []
})
const person = ref<Record<TemplateKind, string>>({
  'marks-summary': '',
  certificate: '',
  'mentor-certificate': ''
})

const loadPeople = async () => {
  await Promise.all(
    (Object.keys(PICKED) as TemplateKind[]).map(async (kind) => {
      try {
        people.value[kind] = (await fetchTemplateTestPeople(kind)).options
      } catch {
        // Best-effort: the dropdown just reads Nobody yet.
        people.value[kind] = []
      }
      person.value[kind] = people.value[kind][0]?.value ?? ''
    })
  )
}

// With forPerson, the chosen student's or mentor's real document; otherwise
// made-up details.
const testRender = async (kind: TemplateKind, forPerson = false) => {
  actionError.value = ''
  testing.value = forPerson ? `${kind}-person` : kind
  const candidate = PICKED[kind].value
  const who = forPerson ? person.value[kind] : undefined
  try {
    // A picked file is test-driven as-is; otherwise the saved template runs.
    if (candidate) await downloadCandidateTestRender(kind, candidate, who)
    else await downloadTemplateTestRender(kind, who)
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
    showStoredText(settings.value)
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
  void loadPeople()
})

const clearFilePickers = () => {
  sig1.value = null
  sig2.value = null
  summaryTpl.value = null
  certTpl.value = null
  mentorTpl.value = null
  for (const input of [sig1Input.value, sig2Input.value, summaryInput.value, certInput.value, mentorInput.value]) {
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

// Text-only edits go as JSON; any file present switches the whole PATCH to
// multipart (the API accepts both on the same endpoint).
const save = async () => {
  actionError.value = ''
  savedMessage.value = ''
  isSaving.value = true
  try {
    const hasFile = sig1.value || sig2.value || summaryTpl.value || certTpl.value || mentorTpl.value
    let body: FormData | ReturnType<typeof directorText>
    if (hasFile) {
      const fd = new FormData()
      for (const [field, value] of Object.entries(directorText())) fd.append(field, value)
      if (sig1.value) fd.append('director_1_signature', sig1.value)
      if (sig2.value) fd.append('director_2_signature', sig2.value)
      if (summaryTpl.value) fd.append('marks_summary_template', summaryTpl.value)
      if (certTpl.value) fd.append('certificate_template', certTpl.value)
      if (mentorTpl.value) fd.append('mentor_certificate_template', mentorTpl.value)
      body = fd
    } else {
      body = directorText()
    }
    settings.value = await updateGradingSettings(body)
    showStoredText(settings.value)
    clearFilePickers()
    flashSaved('Files updated.')
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
  font-weight: 600;
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
  gap: 0.9rem;
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

/* Above the Browse row, sized to its label rather than the field. */
.grading-settings__template .grading-settings__download {
  justify-self: start;
  margin-bottom: 0.5rem;
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
/* The theme's brighter success green, so the hint reads clearly as green. */
.grading-settings__found-hint {
  color: var(--success);
}

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
/* Test, then Test Student or Test Mentor with its dropdown. */
.grading-settings__test-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem 1.25rem;
}

/* The button and its dropdown stay together when the line wraps. */
.grading-settings__person-test {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.grading-settings__person-select {
  border: 1px solid var(--border-light);
  border-radius: 6px;
  padding: 0.3rem 0.5rem;
  font-size: 0.85rem;
  font-family: inherit;
  background: var(--surface-elevated);
  color: var(--charcoal);
  max-width: 14rem;
}

.grading-settings__save-hint {
  color: #b8860b;
  font-size: 0.85rem;
  margin: 0;
}

/* Same space above as below: the field's own 0.3rem gap plus this makes the
   0.85rem the next field sits below it. */
.grading-settings__save-hint--director {
  margin-top: 0.55rem;
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
