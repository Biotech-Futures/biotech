<template>
  <div class="content-area system-logs">
    <header class="page-header">
      <h1 class="page-title">System Logs</h1>
      <p class="page-subtitle">
        Warnings, errors, and sign-in and email events the platform has recorded.
        Times are shown in {{ timeZoneLabel }}; exports use UTC.
      </p>
    </header>

    <div class="system-logs__main">
      <p v-if="error" class="system-logs__error" role="alert">
        <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
        <span>{{ error }}</span>
      </p>
      <p v-if="dateRangeError" class="system-logs__error" role="alert">
        <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
        <span>{{ dateRangeError }}</span>
      </p>
      <p v-if="exportError" class="system-logs__error" role="alert">
        <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
        <span>{{ exportError }}</span>
      </p>
      <p v-if="exportLimitNotice" class="system-logs__notice" role="status">
        <i class="fas fa-circle-info" aria-hidden="true"></i>
        <span>{{ exportLimitNotice }}</span>
      </p>

      <AppDataTable
        :columns="columns"
        :rows="tableRows"
        row-key="id"
        :loading="loading"
        :selectable="false"
        :max-page-size="200"
        :page="page"
        :page-size="pageSize"
        :total-count="totalCount"
        v-model:search="searchInput"
        search-placeholder="Search messages"
        :empty-message="emptyMessage"
        @update:page="onPageChange"
        @update:page-size="onPageSizeChange"
      >
        <template #filters>
          <AdminSystemLogsFilters
            :filters="filters"
            :has-active-filters="hasActiveFilters"
            @patch="applyFilterPatch"
            @clear="clearFilters"
          />
        </template>

        <!-- Export exactly what the filters show. -->
        <template #search-side>
          <button
            v-for="option in EXPORTS"
            :key="option.type"
            type="button"
            class="btn btn-outline system-logs__export"
            :disabled="Boolean(exporting) || Boolean(dateRangeError)"
            :aria-busy="exporting === option.type"
            @click="exportLogs(option.type)"
          >
            <i
              class="fas"
              :class="exporting === option.type ? 'fa-spinner fa-spin' : 'fa-download'"
              aria-hidden="true"
            ></i>
            <span>{{ exporting === option.type ? 'Exporting...' : option.label }}</span>
          </button>
        </template>

        <template #cell-time="{ row }">
          <time :datetime="toLog(row).created_at" :title="`${toLog(row).created_at} (UTC)`">
            {{ formatExactTime(toLog(row).created_at) }}
          </time>
        </template>

        <template #cell-level="{ row }">
          <SystemLogLevelBadge :level="toLog(row).level_name" />
        </template>

        <template #cell-source="{ row }">
          <span class="system-logs__code">{{ toLog(row).logger_name }}</span>
        </template>

        <template #cell-message="{ row }">
          <span class="system-logs__message">
            {{ toLog(row).message }}<template v-if="toLog(row).message_truncated">…</template>
          </span>
          <span v-if="toLog(row).has_traceback" class="system-logs__tag" title="Has a traceback">
            <i class="fas fa-bug" aria-hidden="true"></i>
            <span class="sr-only">Has a traceback</span>
          </span>
        </template>

        <template #cell-user="{ row }">
          <span :title="toLog(row).user?.email">{{ userLabel(toLog(row)) }}</span>
        </template>

        <template #cell-request="{ row }">
          <span v-if="toLog(row).request_path" class="system-logs__code">
            {{ toLog(row).request_method }} {{ toLog(row).request_path }}
          </span>
          <span v-else class="system-logs__muted">—</span>
        </template>

        <!-- Opened by the row's chevron or a click on the row. -->
        <template #row-detail="{ row }">
          <AdminSystemLogDetail :log-id="toLog(row).id" />
        </template>
      </AppDataTable>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import AppDataTable, { type DataTableColumn } from '@/components/AppDataTable.vue'
import AdminSystemLogDetail from '@/components/admin/system-logs/AdminSystemLogDetail.vue'
import AdminSystemLogsFilters from '@/components/admin/system-logs/AdminSystemLogsFilters.vue'
import SystemLogLevelBadge from '@/components/admin/system-logs/SystemLogLevelBadge.vue'
import { useAdminSystemLogs } from '@/composables/admin/useAdminSystemLogs'
import type { SystemLogExportType, SystemLogRow } from '@/utils/adminAPI'
import { formatExactTime } from '@/utils/date'

const EXPORTS: { type: SystemLogExportType; label: string }[] = [
  { type: 'csv', label: 'Export CSV' },
  { type: 'json', label: 'Export JSON' }
]

// The server pages and filters; the newest rows come first.
const columns: DataTableColumn[] = [
  { key: 'time', label: 'Time' },
  { key: 'level', label: 'Level' },
  { key: 'source', label: 'Source' },
  { key: 'message', label: 'Message', wrap: true },
  { key: 'user', label: 'User' },
  { key: 'request', label: 'Request' }
]

const {
  rows,
  totalCount,
  page,
  pageSize,
  loading,
  error,
  exporting,
  exportError,
  exportLimitNotice,
  searchInput,
  filters,
  hasActiveFilters,
  dateRangeError,
  timeZoneLabel,
  emptyMessage,
  load,
  applyFilterPatch,
  clearFilters,
  onPageChange,
  onPageSizeChange,
  exportLogs
} = useAdminSystemLogs()

// `time` is what AppDataTable names a row by in its expand button's label
// ("Show details for 15/10/26 16:38:59 ERROR apps.services.mailer"); the cell
// itself is drawn by the cell-time slot.
const tableRows = computed(() =>
  rows.value.map((log) => ({
    ...log,
    time: `${formatExactTime(log.created_at)} ${log.level_name} ${log.logger_name}`
  })) as unknown as Record<string, unknown>[]
)

const toLog = (row: Record<string, unknown>) => row as unknown as SystemLogRow

const userLabel = (log: SystemLogRow) => (log.user ? log.user.name || log.user.email : '—')

onMounted(load)
</script>

<style scoped>
.system-logs__main {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.system-logs__error {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0;
  padding: 0.75rem 1rem;
  border-left: 4px solid var(--danger);
  border-radius: 6px;
  background-color: rgba(220, 53, 69, 0.08);
  color: var(--danger);
}

.system-logs__notice {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0;
  padding: 0.75rem 1rem;
  border-left: 4px solid var(--info);
  border-radius: 6px;
  background-color: rgba(23, 162, 184, 0.08);
  color: inherit;
}

.system-logs__export {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.system-logs__code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.8rem;
}

.system-logs__message {
  overflow-wrap: anywhere;
}

.system-logs__tag {
  margin-left: 0.4rem;
  color: var(--danger);
  font-size: 0.75rem;
}

.system-logs__muted {
  color: var(--text-muted);
}
</style>
