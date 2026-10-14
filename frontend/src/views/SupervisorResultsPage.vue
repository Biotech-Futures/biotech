<template>
  <div class="content-area supervisor-results-page">
    <header class="page-header">
      <h1 class="page-title">Results</h1>
      <p class="page-subtitle">Your students' marks and certificates, and their groups' mentors' certificates.</p>
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
        <AppDataTable
          :columns="markColumns"
          :rows="results.groups"
          row-key="group_id"
          :selectable="false"
          :default-sort="markSort"
          search-placeholder="Group, student or mentor"
          empty-message="None of your students' groups made a submission."
        >
          <template #search-side>
            <button
              type="button"
              class="btn btn-primary"
              :disabled="!results.groups.length || downloading === SHEET"
              @click="downloadSheet"
            >
              {{ downloading === SHEET ? 'Downloading…' : 'Download Marks Spreadsheet' }}
            </button>
          </template>
        </AppDataTable>
      </section>

      <!-- Their students' certificates, and those groups' mentors'. -->
      <!-- By group, then role (students first), then name; the headings
           don't sort. -->
      <section v-if="activeTab === 'certificates'" class="results-section">
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
  downloadSupervisorResultsCertificate,
  downloadSupervisorResultsCertificates,
  downloadSupervisorResultsSheet,
  fetchSupervisorResults,
  type SupervisorResults,
  type SupervisorResultsPerson,
} from '@/utils/managementAPI'

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

const tabs = computed(() => [
  ...(results.value?.marks_released ? [{ id: 'marks' as const, label: 'Marks' }] : []),
  ...(results.value?.certificates_released ? [{ id: 'certificates' as const, label: 'Certificates' }] : []),
])

// The first tab released, when the one open isn't.
watch(tabs, (shown) => {
  if (shown.length && !shown.some((tab) => tab.id === activeTab.value)) activeTab.value = shown[0]!.id
})

// Short text that stays on one line, as wide as it is: a wrapping column is
// at least 14rem.
const ONE_LINE = new Set(['TeamCode', 'Mentor'])

// The spreadsheet's own columns, headed as it heads them: long text wraps,
// marks are numbers, and each mark names its rubric criterion on hover.
const markColumns = computed<DataTableColumn[]>(() =>
  (results.value?.columns ?? []).map((column) => ({
    key: column.key,
    label: column.label,
    title: column.title || undefined,
    type: column.mark ? 'number' : 'string',
    wrap: !column.mark && !ONE_LINE.has(column.key),
  })),
)

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
  download(SHEET, () => downloadSupervisorResultsSheet(results.value?.sheet_file_name || 'BTF_Student_Marks.xlsx'))

const downloadAll = () =>
  download(ALL, () => downloadSupervisorResultsCertificates(results.value?.zip_file_name || 'BTF_Certificates.zip'))

const downloadCertificate = (row: Record<string, unknown>) =>
  download(String(row.key), () => downloadSupervisorResultsCertificate(toPerson(row)))

onMounted(async () => {
  try {
    results.value = await fetchSupervisorResults()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Results could not be loaded.'
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.results-section {
  display: flex;
  flex-direction: column;
}

.results-muted {
  color: var(--text-muted);
}

.results-error {
  color: var(--danger);
}
</style>
