<template>
  <!-- A log row opened in the System Logs table: loads the full row (message,
       traceback, extras) when it opens, as the list only carries a preview. -->
  <div class="log-detail" aria-live="polite">
    <p v-if="loading" class="log-detail__state">
      <i class="fas fa-spinner fa-spin" aria-hidden="true"></i>
      <span>Loading details...</span>
    </p>

    <p v-else-if="error" class="log-detail__state log-detail__state--error" role="alert">
      <span>{{ error }}</span>
      <button type="button" class="btn btn-sm btn-outline" @click="load">Try again</button>
    </p>

    <template v-else-if="entry">
      <dl class="log-detail__meta">
        <div>
          <dt>Time</dt>
          <dd>{{ formatExactTime(entry.created_at) }} <span class="log-detail__muted">({{ timeZoneLabel }})</span></dd>
        </div>
        <div>
          <dt>Level</dt>
          <dd><SystemLogLevelBadge :level="entry.level_name" /></dd>
        </div>
        <div>
          <dt>Source</dt>
          <dd class="log-detail__code">{{ location }}</dd>
        </div>
        <div v-if="entry.request_path">
          <dt>Request</dt>
          <dd class="log-detail__code">
            {{ entry.request_method }} {{ entry.request_path }}<template v-if="entry.status_code"> → {{ entry.status_code }}</template>
          </dd>
        </div>
        <div v-if="entry.request_id">
          <dt>Request ID</dt>
          <dd class="log-detail__code">{{ entry.request_id }}</dd>
        </div>
        <div>
          <dt>User</dt>
          <dd>{{ entry.user ? userLabel(entry.user) : '—' }}</dd>
        </div>
      </dl>

      <h4 class="log-detail__heading">Message</h4>
      <pre class="log-detail__pre">{{ entry.message }}</pre>

      <template v-if="entry.traceback">
        <h4 class="log-detail__heading">Traceback</h4>
        <pre class="log-detail__pre log-detail__pre--traceback">{{ entry.traceback }}</pre>
      </template>

      <template v-if="extraEntries.length">
        <h4 class="log-detail__heading">Extra</h4>
        <dl class="log-detail__extra">
          <div v-for="[key, value] in extraEntries" :key="key">
            <dt class="log-detail__code">{{ key }}</dt>
            <dd class="log-detail__code">{{ formatExtra(value) }}</dd>
          </div>
        </dl>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import SystemLogLevelBadge from '@/components/admin/system-logs/SystemLogLevelBadge.vue'
import { fetchSystemLog, type SystemLogDetail, type SystemLogUser } from '@/utils/adminAPI'
import { logApiError } from '@/utils/apiError'
import { formatExactTime, formatTimeZoneLabel, getSetTimeZone } from '@/utils/date'

const props = defineProps<{ logId: number }>()

const entry = ref<SystemLogDetail | null>(null)
const loading = ref(false)
const error = ref('')

const timeZoneLabel = computed(() => formatTimeZoneLabel(getSetTimeZone()))

const location = computed(() => {
  if (!entry.value) return ''
  const { logger_name: logger, module, func_name: func, line_no: line } = entry.value
  const where = [module, func].filter(Boolean).join('.')
  return where ? `${logger} (${where}${line ? `:${line}` : ''})` : logger
})

const extraEntries = computed(() => Object.entries(entry.value?.extra ?? {}))

const userLabel = (user: SystemLogUser) => (user.name ? `${user.name} (${user.email})` : user.email)

const formatExtra = (value: unknown) =>
  typeof value === 'string' ? value : JSON.stringify(value)

const load = async () => {
  loading.value = true
  error.value = ''
  try {
    entry.value = await fetchSystemLog(props.logId)
  } catch (loadError) {
    logApiError('admin.systemLogs.detail', loadError)
    error.value = loadError instanceof Error ? loadError.message : 'The details could not be loaded.'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.log-detail {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  font-size: 0.875rem;
}

.log-detail__state {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin: 0;
  color: var(--text-muted);
}

.log-detail__state--error {
  color: var(--danger);
}

.log-detail__meta,
.log-detail__extra {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(14rem, 1fr));
  gap: 0.5rem 1.5rem;
  margin: 0;
}

.log-detail__meta dt,
.log-detail__extra dt {
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.log-detail__extra dt {
  text-transform: none;
  letter-spacing: normal;
}

.log-detail__meta dd,
.log-detail__extra dd {
  margin: 0.15rem 0 0;
  overflow-wrap: anywhere;
}

.log-detail__heading {
  margin: 0.4rem 0 0;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.log-detail__pre {
  margin: 0;
  padding: 0.6rem 0.75rem;
  max-height: 24rem;
  overflow: auto;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--bg-light);
  color: var(--teal);
  font-size: 0.8rem;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.log-detail__code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.8rem;
}

.log-detail__muted {
  color: var(--text-muted);
}
</style>
