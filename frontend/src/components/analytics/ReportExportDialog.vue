<template>
  <button ref="trigger" type="button" class="report-export-trigger" @click="openDialog">
    <BtfIcon name="download" />
    Export CSV
  </button>

  <div v-if="open" class="report-export-backdrop" @click.self="closeDialog">
    <section
      ref="dialog"
      class="report-export-dialog"
      role="dialog"
      aria-modal="true"
      aria-labelledby="report-export-title"
      aria-describedby="report-export-description"
      @keydown.esc="closeDialog"
      @keydown.tab="trapFocus"
    >
      <header class="report-export-header">
        <div>
          <h2 id="report-export-title">Export CSV</h2>
          <p id="report-export-description">{{ selectedReport.description }}</p>
        </div>
        <button
          type="button"
          class="report-export-close"
          aria-label="Close export CSV dialog"
          @click="closeDialog"
        >
          ×
        </button>
      </header>

      <p class="report-export-note">
        Reports use live backend data; the analytics charts currently show frontend demo data.
      </p>

      <form @submit.prevent="submit">
        <div class="report-export-grid">
          <label>
            <span>Report</span>
            <select
              id="report-export-type"
              ref="reportSelect"
              v-model="form.report"
              @change="changeReport"
            >
              <option v-for="item in reports" :key="item.value" :value="item.value">
                {{ item.label }}
              </option>
            </select>
          </label>

          <label v-if="form.report === 'participants' || form.report === 'permission'">
            <span>Group by</span>
            <select id="report-export-group" v-model="form.groupBy">
              <option v-for="item in groupOptions" :key="item.value" :value="item.value">
                {{ item.label }}
              </option>
            </select>
          </label>

          <label v-if="usesActivityRange">
            <span>Date range</span>
            <select id="report-export-range" v-model="form.quickRange">
              <option value="24h">Current UTC day</option>
              <option value="7d">Last 7 UTC days</option>
              <option value="14d">Last 14 UTC days</option>
              <option value="custom">Custom dates</option>
            </select>
          </label>

          <label v-if="form.report === 'participants' || form.report === 'login_activity'">
            <span>Role</span>
            <select v-model="form.role">
              <option value="all">All roles</option>
              <option value="student">Student</option>
              <option value="mentor">Mentor</option>
              <option value="supervisor">Supervisor</option>
              <option value="admin">Admin</option>
            </select>
          </label>

          <label v-if="form.report !== 'announcement_delivery'">
            <span>Account status</span>
            <select v-model="form.status">
              <option value="all">All statuses</option>
              <option value="invited">Invited</option>
              <option value="pending">Pending</option>
              <option value="active">Active</option>
              <option value="suspended">Suspended</option>
              <option value="deactivated">Inactive</option>
            </select>
          </label>

          <label v-if="form.report !== 'announcement_delivery'">
            <span>Country</span>
            <select
              v-model="form.countryId"
              :disabled="locationsLoading"
              @change="form.stateId = 'all'"
            >
              <option value="all">All countries</option>
              <option v-for="country in countries" :key="country.id" :value="String(country.id)">
                {{ country.countryName }}
              </option>
            </select>
          </label>

          <label v-if="form.report !== 'announcement_delivery'">
            <span>State</span>
            <select v-model="form.stateId" :disabled="locationsLoading">
              <option value="all">All states</option>
              <option v-for="state in visibleStates" :key="state.id" :value="String(state.id)">
                {{ stateLabel(state) }}
              </option>
            </select>
          </label>

          <label v-if="form.report === 'participants'">
            <span>Interest</span>
            <input
              v-model="form.interest"
              type="text"
              maxlength="255"
              placeholder="Exact interest name"
            />
          </label>

          <label v-if="form.report === 'permission'">
            <span>Permission</span>
            <select v-model="form.permission">
              <option value="all">All permission states</option>
              <option value="granted">Granted</option>
              <option value="not_granted">Not granted</option>
            </select>
          </label>

          <label v-if="form.report === 'announcement_delivery'">
            <span>Delivery status</span>
            <select v-model="form.deliveryStatus">
              <option value="all">All delivery states</option>
              <option value="success">Success</option>
              <option value="partial">Partial</option>
              <option value="failed">Failed</option>
            </select>
          </label>

          <template v-if="showDates">
            <label>
              <span>Start date</span>
              <input v-model="form.startDate" type="date" :max="form.endDate || undefined" />
            </label>
            <label>
              <span>End date</span>
              <input v-model="form.endDate" type="date" :min="form.startDate || undefined" />
            </label>
          </template>
        </div>

        <p v-if="locationError" class="report-export-warning" role="status">
          {{ locationError }}
        </p>
        <p
          v-if="notice"
          :class="notice.error ? 'report-export-error' : 'report-export-success'"
          :role="notice.error ? 'alert' : 'status'"
        >
          {{ notice.text }}
        </p>

        <footer class="report-export-actions">
          <button type="button" class="report-export-cancel" @click="closeDialog">Cancel</button>
          <button type="submit" class="report-export-download" :disabled="downloading">
            {{ downloading ? 'Preparing CSV…' : 'Download CSV' }}
          </button>
        </footer>
      </form>
    </section>
  </div>
</template>

<script setup lang="ts">
import BtfIcon from '@/components/BtfIcon.vue'
import { computed, nextTick, reactive, ref } from 'vue'

import {
  buildReportExportParams,
  downloadReportCsv,
  loadReportLocations,
  validateReportExportForm,
  type ReportCountry,
  type ReportExportForm,
  type ReportState,
  type ReportType,
} from '@/utils/reportExport'

const reports: Array<{ value: ReportType; label: string; description: string }> = [
  {
    value: 'participants',
    label: 'Participant overview',
    description: 'Counts and percentages by role, status, interest or region.',
  },
  {
    value: 'permission',
    label: 'Permission compliance',
    description: 'Student join-permission totals and rates without personal data.',
  },
  {
    value: 'login_activity',
    label: 'Login activity',
    description: 'Successful logins and unique logged-in users in UTC day buckets.',
  },
  {
    value: 'announcement_delivery',
    label: 'Announcement delivery',
    description: 'Delivery totals and rates without recipient or provider details.',
  },
]

const participantGroups = [
  { value: 'role', label: 'Role' },
  { value: 'status', label: 'Account status' },
  { value: 'interest', label: 'Interest' },
  { value: 'country', label: 'Country' },
  { value: 'state', label: 'State' },
]
const permissionGroups = [
  { value: 'none', label: 'Overall' },
  { value: 'country', label: 'Country' },
  { value: 'state', label: 'State' },
]

const form = reactive<ReportExportForm>({
  report: 'participants',
  groupBy: 'role',
  quickRange: '7d',
  startDate: '',
  endDate: '',
  role: 'all',
  status: 'all',
  countryId: 'all',
  stateId: 'all',
  interest: '',
  permission: 'all',
  deliveryStatus: 'all',
})
const open = ref(false)
const downloading = ref(false)
const locationsLoading = ref(false)
const locationsLoaded = ref(false)
const locationError = ref('')
const countries = ref<ReportCountry[]>([])
const states = ref<ReportState[]>([])
const notice = ref<{ text: string; error: boolean } | null>(null)
const trigger = ref<HTMLButtonElement | null>(null)
const dialog = ref<HTMLElement | null>(null)
const reportSelect = ref<HTMLSelectElement | null>(null)

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

const selectedReport = computed(() => reports.find((item) => item.value === form.report)!)
const groupOptions = computed(() =>
  form.report === 'participants' ? participantGroups : permissionGroups,
)
const usesActivityRange = computed(
  () => form.report === 'login_activity' || form.report === 'announcement_delivery',
)
const showDates = computed(
  () => form.report === 'participants' || (usesActivityRange.value && form.quickRange === 'custom'),
)
const selectedCountry = computed(() =>
  countries.value.find((country) => String(country.id) === form.countryId),
)
const visibleStates = computed(() =>
  selectedCountry.value
    ? states.value.filter((state) => state.countryName === selectedCountry.value?.countryName)
    : states.value,
)

async function openDialog() {
  open.value = true
  notice.value = null
  await nextTick()
  reportSelect.value?.focus()
  if (locationsLoaded.value || locationsLoading.value) return

  locationsLoading.value = true
  locationError.value = ''
  try {
    const locations = await loadReportLocations()
    countries.value = locations.countries
    states.value = locations.states
    locationsLoaded.value = true
  } catch {
    locationError.value = 'Location filters could not be loaded. You can still export without them.'
  } finally {
    locationsLoading.value = false
  }
}

async function closeDialog() {
  open.value = false
  await nextTick()
  trigger.value?.focus()
}

function trapFocus(event: KeyboardEvent) {
  const focusable = Array.from(
    dialog.value?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR) ?? [],
  )
  if (!focusable.length) return

  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}

function changeReport() {
  notice.value = null
  if (form.report === 'participants') form.groupBy = 'role'
  if (form.report === 'permission') form.groupBy = 'state'
}

async function submit() {
  notice.value = null
  const error = validateReportExportForm(form)
  if (error) {
    notice.value = { text: error, error: true }
    return
  }

  downloading.value = true
  try {
    await downloadReportCsv(buildReportExportParams(form), form.report)
    notice.value = { text: 'CSV download started.', error: false }
  } catch (error) {
    notice.value = {
      text: error instanceof Error ? error.message : 'The report could not be downloaded.',
      error: true,
    }
  } finally {
    downloading.value = false
  }
}

function stateLabel(state: ReportState) {
  return selectedCountry.value ? state.stateName : `${state.stateName} · ${state.countryName}`
}
</script>

<style scoped>
.report-export-trigger {
  display: inline-flex;
  width: 150px;
  height: 46px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0 16px;
  border: 1px solid #9fd8c7;
  border-radius: 12px;
  background: var(--btf-white);
  color: var(--btf-dark-green);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.report-export-trigger:hover {
  background: #ecf8f4;
}

.report-export-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  padding: 16px;
  background: rgb(8 31 27 / 55%);
}

.report-export-dialog {
  width: min(820px, 100%);
  max-height: calc(100vh - 32px);
  overflow-y: auto;
  padding: 24px;
  border-radius: 14px;
  background: var(--btf-white);
  color: #153f3c;
  box-shadow: 0 24px 60px rgb(0 0 0 / 22%);
}

.report-export-header {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 20px;
}

.report-export-header h2 {
  margin: 0;
  font-size: 24px;
}
.report-export-header p {
  margin: 6px 0 0;
  color: #617572;
}

.report-export-close {
  width: 36px;
  height: 36px;
  border: 0;
  border-radius: 8px;
  background: #f2f6f5;
  color: #355652;
  font-size: 24px;
  cursor: pointer;
}

.report-export-note {
  margin: 18px 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: #fff7df;
  color: #795d0b;
  font-size: 13px;
}

.report-export-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 14px;
}

.report-export-grid label {
  display: grid;
  gap: 6px;
}
.report-export-grid label span {
  color: #425e59;
  font-size: 12px;
  font-weight: 600;
}
.report-export-grid select,
.report-export-grid input {
  width: 100%;
  height: 40px;
  padding: 0 10px;
  border: 1px solid #d7e3e0;
  border-radius: 8px;
  background: var(--btf-white);
  color: #234844;
  font: inherit;
}

.report-export-grid select:disabled {
  background: #f2f5f4;
  cursor: wait;
}
.report-export-warning,
.report-export-error,
.report-export-success {
  margin: 14px 0 0;
  font-size: 13px;
}
.report-export-warning {
  color: #795d0b;
}
.report-export-error {
  color: #b42318;
}
.report-export-success {
  color: #08765d;
}

.report-export-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 22px;
}

.report-export-actions button {
  height: 40px;
  padding: 0 16px;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
}

.report-export-cancel {
  border: 1px solid #ccd9d6;
  background: var(--btf-white);
  color: #355652;
}
.report-export-download {
  border: 1px solid #08765d;
  background: #08765d;
  color: var(--btf-white);
}
.report-export-download:disabled {
  cursor: wait;
  opacity: 0.65;
}

@media (max-width: 780px) {
  .report-export-trigger {
    flex: 1;
    width: auto;
  }
  .report-export-dialog {
    padding: 18px;
  }
}
</style>
