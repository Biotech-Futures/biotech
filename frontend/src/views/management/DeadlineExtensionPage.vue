<template>
  <div class="extensions">
    <section class="card">
      <div class="card-header">
        <h3 class="card-title">Extend Deadline</h3>
      </div>
      <p class="extensions__hint">
        Search by the group's name to extend their deadline. Times are in your local
        timezone ({{ localTimeZone }}). Students see the closing time; the server quietly
        keeps accepting for the grace hours after it.
      </p>
      <!-- Granting is the Grant button only: Enter in a field (e.g. the
           search box) must never grant an extension. -->
      <form class="extensions__form" @submit.prevent>
        <label class="extensions__field extensions__field--group">
          <span>Search</span>
          <GroupSearchInput ref="picker" v-model="groupQuery" />
        </label>
        <label class="extensions__field">
          <span>Extended until</span>
          <input
            v-model="untilLocal"
            type="datetime-local"
            :min="minLocal || undefined"
            required
            class="extensions__input"
          />
        </label>
        <label class="extensions__field">
          <span>Grace hours</span>
          <input
            v-model.number="graceHours"
            type="number"
            min="0"
            max="72"
            class="extensions__input extensions__input--grace"
          />
        </label>
        <label class="extensions__field extensions__field--reason">
          <span>Reason (optional)</span>
          <textarea
            v-model="reason"
            rows="3"
            placeholder="e.g. school closure"
            class="extensions__input extensions__input--reason"
          ></textarea>
        </label>
        <button
          type="button"
          class="btn btn-primary btn-sm"
          :disabled="isSaving || !groupQuery || !untilLocal"
          @click="save"
        >
          {{ isSaving ? 'Saving…' : 'Grant' }}
        </button>
      </form>
      <p v-if="actionError" class="extensions__banner extensions__banner--error">{{ actionError }}</p>
      <p v-if="savedMessage" class="extensions__banner extensions__banner--ok">{{ savedMessage }}</p>
    </section>

    <section class="card">
      <h3 class="extensions__section-title">Current Extensions</h3>
      <p v-if="isLoading" class="extensions__hint">Loading…</p>
      <div v-else-if="loadError" class="extensions__load-error">
        <p>Failed to load. {{ loadError }}</p>
        <button type="button" class="btn btn-outline btn-sm" @click="load">Try again</button>
      </div>
      <!-- Kept in the server's order: the page owns sorting, and sorts nothing. -->
      <AppDataTable
        v-else
        :columns="extensionColumns"
        :rows="extensionRows"
        row-key="id"
        :selectable="false"
        :page-size="DATA_TABLE_ALL"
        :sort="{ key: '', direction: 'asc' }"
        search-placeholder="Group name"
        empty-message="No extensions granted."
        :action-columns="1"
        show-all-details
        :detail-for="(row) => Boolean(row.reason)"
        :row-class="(row) => (row.reason ? 'extensions__row--with-reason' : undefined)"
      >
        <template #cell-group="{ row }">
          <span class="extensions__cell--strong">{{ row.group }}</span>
        </template>
        <template #cell-status="{ row }">
          <span :class="`extensions__status--${extensionOf(row).status.state}`">
            {{ row.status }}
          </span>
        </template>
        <template #actions="{ row }">
          <span v-if="extensionOf(row).revoked_at" class="extensions__muted">Revoked</span>
          <!-- Past its grace period there's nothing left to revoke. -->
          <span v-else-if="extensionOf(row).status.state === 'expired'" class="extensions__muted">
            Expired
          </span>
          <button
            v-else
            type="button"
            class="btn btn-outline btn-sm"
            :disabled="isSaving"
            @click="pendingRevoke = extensionOf(row)"
          >
            Revoke
          </button>
        </template>
        <!-- The reason gets a full-width row of its own so multi-line text
             can wrap; the pair reads as one record. -->
        <template #row-detail="{ row }">
          <div class="extensions__reason">
            <span class="extensions__muted">Reason:</span> {{ row.reason }}
          </div>
        </template>
      </AppDataTable>
    </section>

    <div v-if="overwriteWarning" class="extensions__overlay" @click.self="overwriteWarning = null">
      <div
        class="extensions__dialog"
        role="dialog"
        aria-modal="true"
        aria-label="Extension already exists"
      >
        <h4 class="extensions__dialog-title">This group already has an extension</h4>
        <p class="extensions__dialog-body">
          <strong>{{ overwriteWarning.groupName }}</strong> is already extended until
          <strong>{{ overwriteWarning.until }}</strong>. Granting a new extension replaces
          the current one.
        </p>
        <div class="extensions__dialog-actions">
          <button type="button" class="btn btn-outline btn-sm" @click="overwriteWarning = null">
            Cancel
          </button>
          <button
            type="button"
            class="btn btn-primary btn-sm"
            :disabled="isSaving"
            @click="performSave(overwriteWarning.id)"
          >
            {{ isSaving ? 'Saving…' : 'Replace extension' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="pendingRevoke" class="extensions__overlay" @click.self="pendingRevoke = null">
      <div class="extensions__dialog" role="dialog" aria-modal="true" aria-label="Revoke extension">
        <h4 class="extensions__dialog-title">Revoke this extension?</h4>
        <p class="extensions__dialog-body">
          <strong>{{ pendingRevoke.group_name }}</strong> is extended until
          <strong>{{ untilLabel(pendingRevoke.extended_until) }}</strong>. Revoking it puts the
          group back on the standard submission deadline.
        </p>
        <div class="extensions__dialog-actions">
          <button type="button" class="btn btn-outline btn-sm" @click="pendingRevoke = null">
            Cancel
          </button>
          <button
            type="button"
            class="btn btn-primary btn-sm"
            :disabled="isSaving"
            @click="revoke(pendingRevoke.group_id)"
          >
            {{ isSaving ? 'Revoking…' : 'Revoke extension' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AppDataTable, { type DataTableColumn } from '@/components/AppDataTable.vue'
import { useFlashMessage } from '@/composables/useFlashMessage'
import {
  fetchGroupExtensions,
  fetchSubmissionDeadline,
  removeGroupExtension,
  saveGroupExtension,
  type GroupExtension
} from '@/utils/managementAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { DATA_TABLE_ALL } from '@/utils/dataTable'
import { describeBrowserTimeZone } from '@/utils/date'
import GroupSearchInput from '@/components/grading/GroupSearchInput.vue'

const localTimeZone = describeBrowserTimeZone()

const extensions = ref<GroupExtension[]>([])
const isLoading = ref(false)
const loadError = ref('')
const actionError = ref('')
const { message: savedMessage, show: flashSaved } = useFlashMessage()
const isSaving = ref(false)

const picker = ref<InstanceType<typeof GroupSearchInput> | null>(null)
const groupQuery = ref('')
// Defaults to today at 23:59 — extensions are almost always end-of-day,
// so the admin only has to adjust the date.
const defaultUntilLocal = () => {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T23:59`
}
const untilLocal = ref(defaultUntilLocal())
const graceHours = ref(24)
const reason = ref('')

// Active until the extended date; In grace while the extension's own grace
// hours still accept; Expired after that — mirroring the deadline card.
const extensionStatus = (e: {
  extended_until: string
  grace_hours: number
  revoked_at: string | null
}) => {
  if (e.revoked_at) return { state: 'expired', label: 'Revoked' }
  const until = new Date(e.extended_until).getTime()
  const graceEnd = until + (e.grace_hours || 0) * 3_600_000
  const now = Date.now()
  if (now <= until) return { state: 'active', label: 'Active' }
  if (now <= graceEnd) return { state: 'grace', label: 'In grace' }
  return { state: 'expired', label: 'Expired' }
}

const extensionColumns: DataTableColumn[] = [
  { key: 'group', label: 'Group', sortable: false },
  { key: 'until', label: 'Extension', sortable: false },
  // Past the normal deadline, grace aside: "1d 18h".
  { key: 'added', label: 'Added', sortable: false },
  { key: 'grace', label: 'Grace', sortable: false },
  { key: 'status', label: 'Status', sortable: false },
  { key: 'grantedBy', label: 'Granted by', sortable: false },
  { key: 'revokedBy', label: 'Revoked by', sortable: false }
]

const formatUntil = (iso: string) => {
  const at = new Date(iso)
  const date = at.toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: '2-digit' })
  const time = at.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })
  return `${date} ${time}`
}

// Each extension as a table row: plain text for each column, so Search can
// match it, and the extension itself for the cells drawn here.
const extensionRows = computed(() =>
  extensions.value.map((e) => {
    const status = extensionStatus(e)
    return {
      id: e.id,
      record: { ...e, status },
      group: e.group_name,
      until: formatUntil(e.extended_until),
      added: e.added ?? '—',
      grace: e.grace_hours ? `+${e.grace_hours}h` : '—',
      status: status.label,
      grantedBy: e.granted_by ?? '—',
      revokedBy: e.revoked_by ?? '—',
      reason: e.reason
    }
  })
)

const extensionOf = (row: Record<string, unknown>) =>
  row.record as GroupExtension & { status: ReturnType<typeof extensionStatus> }

// Picker floor: the calendar refuses anything at or before the current
// deadline (an earlier "extension" would shorten the team's window). The
// server enforces the same rule as backstop.
const minLocal = ref('')

const loadDeadlineFloor = async () => {
  try {
    const deadline = (await fetchSubmissionDeadline()).deadline
    if (deadline) {
      const d = new Date(deadline.closes_at)
      const pad = (n: number) => String(n).padStart(2, '0')
      minLocal.value = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
    }
  } catch {
    minLocal.value = ''
  }
}

const load = async () => {
  isLoading.value = true
  loadError.value = ''
  try {
    extensions.value = (await fetchGroupExtensions()).extensions
  } catch (err) {
    extensions.value = []
    loadError.value = apiErrorFromUnknown(err).message
  } finally {
    isLoading.value = false
  }
}

// Warning shown when the picked group already has an active extension —
// granting again replaces it, so the admin must confirm on purpose.
const overwriteWarning = ref<{ id: number; groupName: string; until: string } | null>(null)

const save = async () => {
  actionError.value = ''
  savedMessage.value = ''
  const id = picker.value?.resolveId() ?? null
  if (id == null) {
    actionError.value = 'No group matches that name.'
    return
  }
  const existing = extensions.value.find((e) => e.group_id === id && !e.revoked_at)
  if (existing) {
    overwriteWarning.value = {
      id,
      groupName: existing.group_name,
      until: `${new Date(existing.extended_until).toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: '2-digit' })} ${new Date(existing.extended_until).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })}`
    }
    return
  }
  await performSave(id)
}

const performSave = async (id: number) => {
  isSaving.value = true
  try {
    const iso = new Date(untilLocal.value).toISOString()
    await saveGroupExtension(id, iso, graceHours.value || 0, reason.value)
    flashSaved('Extension granted.')
    groupQuery.value = ''
    untilLocal.value = defaultUntilLocal()
    graceHours.value = 24
    reason.value = ''
    await load()
  } catch (err) {
    actionError.value = apiErrorFromUnknown(err).message
  } finally {
    isSaving.value = false
    overwriteWarning.value = null
  }
}

// Revoke asks first: the row's button opens the popup, its confirm revokes.
const pendingRevoke = ref<GroupExtension | null>(null)

// "05/11/26 13:00", the same format as the table's Extension column.
const untilLabel = (iso: string) => {
  const d = new Date(iso)
  return `${d.toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: '2-digit' })} ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })}`
}

const revoke = async (id: number) => {
  actionError.value = ''
  savedMessage.value = ''
  isSaving.value = true
  try {
    await removeGroupExtension(id)
    await load()
  } catch (err) {
    actionError.value = apiErrorFromUnknown(err).message
  } finally {
    isSaving.value = false
    pendingRevoke.value = null
  }
}

onMounted(() => {
  void load()
  void loadDeadlineFloor()
})
</script>

<style scoped>
/* A section heading, as "Set Details" on Notify Finalists. */
.extensions__section-title {
  font-size: 1.05rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
}

.extensions {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.extensions__hint {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin-bottom: 0.75rem;
}

.extensions__form {
  display: flex;
  align-items: flex-end;
  gap: 1rem;
  flex-wrap: wrap;
}

.extensions__field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.85rem;
  color: var(--teal);
}

.extensions__status--active {
  color: var(--dark-green);
  font-weight: 600;
}

/* Same yellow as the deadline card's grace state. */
.extensions__status--grace {
  color: #eab308;
  font-weight: 600;
}

.extensions__status--expired {
  color: var(--text-muted);
  font-weight: 600;
}

/* Full row of its own, below the other fields. */
.extensions__field--reason {
  flex-basis: 100%;
}

.extensions__input--reason {
  resize: vertical;
  min-height: 4.5rem;
  font-family: inherit;
}

.extensions__input {
  border: 1px solid var(--border-light);
  border-radius: 6px;
  padding: 0.45rem 0.6rem;
  font-size: 0.9rem;
  font-family: inherit;
  background: var(--surface-elevated);
  color: var(--teal);
}

.extensions__input:focus {
  outline: none;
  border-color: var(--dark-green);
}

.extensions__field--group {
  width: 16rem;
}

.extensions__input--grace {
  width: 5.5rem;
}

.extensions__banner {
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  margin: 0.75rem 0 0;
}

.extensions__banner--error {
  background: color-mix(in srgb, var(--danger) 12%, transparent);
  color: var(--danger);
}

.extensions__banner--ok {
  background: var(--accent-green-soft);
  color: var(--dark-green);
}

.extensions__load-error {
  color: var(--danger);
}

/* A row followed by its reason reads as one record: no line between them. */
:deep(.extensions__row--with-reason) td {
  border-bottom: none;
}

.extensions__reason {
  font-size: 0.85rem;
}

.extensions__cell--strong {
  font-weight: 600;
}

.extensions__muted {
  color: var(--text-muted);
}

/* Replace-extension warning — same treatment as the deadline confirm. */
.extensions__overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  z-index: 2000;
}

.extensions__dialog {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
  padding: 1.25rem 1.5rem;
  max-width: 26rem;
  width: 100%;
}

.extensions__dialog-title {
  margin: 0 0 0.5rem;
  font-size: 1.05rem;
}

.extensions__dialog-body {
  margin: 0 0 1rem;
  font-size: 0.9rem;
  color: var(--teal);
}

.extensions__dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}
</style>
