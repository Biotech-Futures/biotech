<template>
  <!-- A supervisor's own page, or, for admins, Management's Results tab:
       every group's, in a card as the other tabs are. -->
  <div :class="admin ? 'card all-results' : 'content-area supervisor-results-page'">
    <template v-if="admin">
      <div class="card-header">
        <h3 class="card-title">Results</h3>
      </div>
      <p class="results-muted">
        Every group that made a submission: its marks, and its students' and mentors' certificates.
        Shown here before they're released too.
      </p>
    </template>
    <header v-else class="page-header">
      <h1 class="page-title">Results</h1>
      <p class="page-subtitle">Your groups' marks and certificates.</p>
    </header>

    <p v-if="notice" class="results-error" role="alert">{{ notice }}</p>
    <p v-if="loading" class="results-muted">Loading results...</p>
    <p v-else-if="error" class="results-error" role="alert">{{ error }}</p>

    <template v-else-if="results">
      <!-- Only what's released: the marks, the certificates, or both. -->
      <nav v-if="tabs.length" class="tab-bar" role="tablist" aria-label="Results">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          type="button"
          role="tab"
          :aria-selected="activeTab === tab.id"
          class="tab-pill"
          :class="{ active: activeTab === tab.id }"
          @click="activeTab = tab.id"
        >
          {{ tab.label }}
        </button>
      </nav>

      <!-- The spreadsheet their results email carries: a row per group. -->
      <section v-if="activeTab === 'marks'" class="results-section">
        <p v-if="admin && !results.marks_released" class="results-muted" data-test="marks-unreleased">
          Marks haven't been released yet: students and supervisors can't see them.
        </p>
        <AppDataTable
          :columns="shownMarkColumns"
          :search-columns="markColumns"
          :rows="results.groups"
          row-key="group_id"
          :selectable="false"
          :default-sort="markSort"
          search-placeholder="Group, student or mentor"
          :empty-message="admin ? 'No group made a submission.' : 'None of your students\' groups made a submission.'"
        >
          <template #search-side>
            <div class="marks-actions">
              <!-- Only Group and the marks, or every column again. -->
              <button
                type="button"
                class="btn btn-outline"
                :aria-pressed="marksOnly"
                data-test="marks-only"
                @click="marksOnly = !marksOnly"
              >
                {{ marksOnly ? 'Show all columns' : 'Show marks only' }}
              </button>
              <button
                type="button"
                class="btn btn-primary"
                :disabled="!results.groups.length || downloading === SHEET"
                @click="downloadSheet"
              >
                {{ downloading === SHEET ? 'Downloading…' : 'Download Marks Spreadsheet' }}
              </button>
            </div>
          </template>
        </AppDataTable>
      </section>

      <!-- Their students' certificates, and those groups' mentors'. -->
      <!-- By group, then role (students first), then name; the headings
           don't sort. -->
      <section v-if="activeTab === 'certificates'" class="results-section">
        <p v-if="admin && !results.certificates_released" class="results-muted" data-test="certificates-unreleased">
          Certificates haven't been released yet: students and supervisors can't see them.
        </p>
        <AppDataTable
          :columns="peopleColumns"
          :rows="peopleRows"
          row-key="key"
          :selectable="false"
          :sort="NO_SORT"
          :action-headings="['Certificate']"
          search-placeholder="Name or group"
          empty-message="No certificates to show."
        >
          <template #search-side>
            <button
              type="button"
              class="btn btn-primary"
              :disabled="!downloadable || downloading === ALL"
              @click="downloadAll"
            >
              {{ downloading === ALL ? 'Downloading…' : 'Download All Certificates' }}
            </button>
          </template>
          <template #actions="{ row }">
            <!-- A finalist group's, while certificates go out without finalists. -->
            <span v-if="toPerson(row).withheld" class="results-muted">Will be Released Separately</span>
            <button
              v-else
              type="button"
              class="btn btn-sm btn-outline"
              :disabled="downloading === row.key"
              @click="downloadCertificate(row)"
            >
              {{ downloading === row.key ? 'Downloading…' : 'Download' }}
            </button>
          </template>
        </AppDataTable>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import AppDataTable, { type DataTableColumn, type DataTableSort } from '@/components/AppDataTable.vue'
import {
  downloadAllResultsCertificate,
  downloadAllResultsCertificates,
  downloadAllResultsSheet,
  downloadSupervisorResultsCertificate,
  downloadSupervisorResultsCertificates,
  downloadSupervisorResultsSheet,
  fetchAllResults,
  fetchSupervisorResults,
  type SupervisorResults,
  type SupervisorResultsPerson,
} from '@/utils/managementAPI'

const props = defineProps<{
  /** Management's Results tab: every group's, released or not. */
  admin?: boolean
}>()

// Every group's for admins; a supervisor's own students' groups' otherwise.
const api = props.admin
  ? {
      fetch: fetchAllResults,
      sheet: downloadAllResultsSheet,
      certificate: downloadAllResultsCertificate,
      certificates: downloadAllResultsCertificates,
    }
  : {
      fetch: fetchSupervisorResults,
      sheet: downloadSupervisorResultsSheet,
      certificate: downloadSupervisorResultsCertificate,
      certificates: downloadSupervisorResultsCertificates,
    }

type TabId = 'marks' | 'certificates'

// What's downloading: the spreadsheet, every certificate, or one row's.
const SHEET = 'sheet'
const ALL = 'all'

const results = ref<SupervisorResults | null>(null)
const loading = ref(true)
const error = ref('')
const notice = ref('')
const downloading = ref<string | null>(null)
const activeTab = ref<TabId>('marks')

// An admin sees both, released or not.
const tabs = computed(() => [
  ...(props.admin || results.value?.marks_released ? [{ id: 'marks' as const, label: 'Marks' }] : []),
  ...(props.admin || results.value?.certificates_released
    ? [{ id: 'certificates' as const, label: 'Certificates' }]
    : []),
])

// The first tab released, when the one open isn't.
watch(tabs, (shown) => {
  if (shown.length && !shown.some((tab) => tab.id === activeTab.value)) activeTab.value = shown[0]!.id
})

// Short text that stays on one line, as wide as it is: a wrapping column is
// at least 14rem.
const ONE_LINE = new Set(['TeamCode', 'Mentor'])

// A criterion's mark (PM1-10, SM1-4), out of 5.
const CRITERION = /^(PM|SM)\d+$/

/** "mark-score-3": a mark's colour on the red (0) to green (5) scale; none when blank. */
const scoreClass = (value: unknown) => {
  const mark = Number.parseFloat(String(value ?? ''))
  if (!Number.isFinite(mark)) return undefined
  return `mark-score-${Math.min(5, Math.max(0, Math.round(mark)))}`
}

// The spreadsheet's own columns, headed as it heads them: long text wraps,
// marks are numbers centred in their cells, and each mark names its rubric
// criterion on hover.
const markColumns = computed<DataTableColumn[]>(() =>
  (results.value?.columns ?? []).map((column) => ({
    key: column.key,
    label: column.label,
    title: column.title || undefined,
    type: column.mark ? 'number' : 'string',
    wrap: !column.mark && !ONE_LINE.has(column.key),
    headClass: column.mark ? 'mark-col' : undefined,
    // Each criterion's mark coloured from red (0) to green (5).
    cellClass: column.mark
      ? (row) => ['mark-col', CRITERION.test(column.key) && scoreClass(row[column.key])].filter(Boolean).join(' ')
      : undefined,
  })),
)

// Show marks only: Group and the marks (PM1-10, SM1-4, MTotal), the rest hidden.
// Search still looks through every column.
const marksOnly = ref(false)
const shownMarkColumns = computed<DataTableColumn[]>(() => {
  if (!marksOnly.value) return markColumns.value
  const marks = new Set((results.value?.columns ?? []).filter((column) => column.mark).map((column) => column.key))
  return markColumns.value.filter((column) => column.key === 'TeamCode' || marks.has(column.key))
})

// Highest total first, as the spreadsheet is.
const markSort = computed<DataTableSort | undefined>(() =>
  results.value?.columns.some((column) => column.key === 'MTotal') ? { key: 'MTotal', direction: 'desc' } : undefined,
)

const peopleColumns: DataTableColumn[] = [
  { key: 'group', label: 'Group', sortable: false },
  { key: 'role', label: 'Role', sortable: false },
  { key: 'name', label: 'Name', sortable: false },
]

// Given, so the table keeps the order below rather than sorting.
const NO_SORT: DataTableSort = { key: '', direction: 'asc' }
const ROLE_ORDER = { student: 0, mentor: 1 }
// "BTF2" before "BTF10".
const byText = (a: string, b: string) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' })

const peopleRows = computed(() =>
  [...(results.value?.people ?? [])]
    .sort(
      (a, b) =>
        byText(a.group_name, b.group_name) || ROLE_ORDER[a.kind] - ROLE_ORDER[b.kind] || byText(a.name, b.name),
    )
    .map((person) => ({
      // A mentor of two groups has a certificate for each.
      key: `${person.group_id}-${person.user_id}`,
      name: person.name,
      role: person.kind === 'student' ? 'Student' : 'Mentor',
      group: person.group_name,
      person,
    })),
)

const toPerson = (row: Record<string, unknown>) => row.person as SupervisorResultsPerson

// Any certificate that isn't released separately.
const downloadable = computed(() => (results.value?.people ?? []).some((person) => !person.withheld))

const download = async (what: string, run: () => Promise<void>) => {
  downloading.value = what
  notice.value = ''
  try {
    await run()
  } catch (err) {
    notice.value = err instanceof Error ? err.message : 'The download failed. Try again.'
  } finally {
    downloading.value = null
  }
}

const downloadSheet = () =>
  download(SHEET, () => api.sheet(results.value?.sheet_file_name || 'BTF_Student_Marks.xlsx'))

const downloadAll = () => download(ALL, () => api.certificates(results.value?.zip_file_name || 'BTF_Certificates.zip'))

const downloadCertificate = (row: Record<string, unknown>) =>
  download(String(row.key), () => api.certificate(toPerson(row)))

onMounted(async () => {
  try {
    results.value = await api.fetch()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Results could not be loaded.'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
/* The marks' columns as narrow as their headings, with no space either
   side, and each mark centred under its heading. */
:deep(.mark-col) {
  padding-left: 0;
  padding-right: 0;
}
:deep(td.mark-col > .data-table-cell) {
  margin-inline: auto;
}

/* A criterion's mark, red (0) through yellow to green (5), with dark text
   in either theme. It keeps its colour when the row is hovered: only Group
   and MTotal turn light green. Each colour spills 1px into the next cell,
   as the table's own row colours do. */
:deep(tr.data-table-row > td.mark-col[class*='mark-score-']) {
  color: #1f2a24;
  background-color: var(--mark-score);
  box-shadow: 1px 0 0 var(--mark-score);
}
:deep(.mark-score-0) { --mark-score: #f2a7a3; }
:deep(.mark-score-1) { --mark-score: #f7c1a3; }
:deep(.mark-score-2) { --mark-score: #fcdba3; }
:deep(.mark-score-3) { --mark-score: #eee6a5; }
:deep(.mark-score-4) { --mark-score: #cbe1aa; }
:deep(.mark-score-5) { --mark-score: #a9dcaf; }

/* Show marks only, then Download, side by side. */
.marks-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.75rem;
}

.results-section {
  display: flex;
  flex-direction: column;
}

.all-results .tab-bar {
  margin-top: 1rem;
}

.results-muted {
  color: var(--text-muted);
}

.results-error {
  color: var(--danger);
}
</style>
