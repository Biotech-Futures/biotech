<template>
  <!-- Late links: one student registers on their own with each, once, for 3
       days, while registration is closed. Made and listed in one card, as
       Presentation Times are. -->
  <section class="card late-links">
    <!-- Headed as a Management page's first card is (Late Registration's). -->
    <div class="card-header">
      <h3 class="card-title">Late Registration Links</h3>
    </div>
    <p class="late-links__hint">
      A late link lets one student register on their own while registration is closed. Each link
      works once, for 3 days.
    </p>

    <form class="late-links__form" @submit.prevent="create">
      <button type="submit" class="btn btn-primary btn-field" :disabled="isCreating">
        {{ isCreating ? 'Creating…' : 'Create Late Link' }}
      </button>
    </form>

    <!-- The new link, to copy and send. -->
    <div v-if="created?.url" class="late-links__created" data-test="late-link-created">
      <span class="late-links__url">{{ created.url }}</span>
      <button type="button" class="btn btn-outline btn-field" @click="copy(created.url, created.id)">
        <i
          :class="copiedId === created.id ? 'fas fa-check' : 'fas fa-copy'"
          aria-hidden="true"
        ></i>
        {{ copiedId === created.id ? 'Copied' : 'Copy' }}
      </button>
    </div>

    <p v-if="error" class="late-links__error" role="alert">{{ error }}</p>

    <p v-if="isLoading" class="late-links__hint">Loading…</p>
    <!-- As Presentation Times: every link at once, newest first, with no
       search or pages. -->
    <AppSimpleTable
      v-else
      :columns="columns"
      :rows="rows"
      row-key="id"
      empty-message="No late links yet."
    >
      <template #cell-status="{ row }">
        <span class="late-links__status" :class="`late-links__status--${toLink(row).status}`">
          {{ row.status }}
        </span>
      </template>
      <!-- While it can be used: Copy, and Revoke. After, nothing to do. -->
      <template #actions="{ row }">
        <div v-if="toLink(row).status === 'active'" class="late-links__actions">
          <button
            v-if="toLink(row).url"
            type="button"
            class="btn btn-outline btn-sm"
            @click="copy(toLink(row).url!, toLink(row).id)"
          >
            <i
              :class="copiedId === toLink(row).id ? 'fas fa-check' : 'fas fa-copy'"
              aria-hidden="true"
            ></i>
            {{ copiedId === toLink(row).id ? 'Copied' : 'Copy' }}
          </button>
          <button
            type="button"
            class="btn btn-outline btn-sm"
            :disabled="revokingId === toLink(row).id"
            @click="revoke(toLink(row))"
          >
            Revoke
          </button>
        </div>
        <span v-else class="late-links__muted">{{ row.status }}</span>
      </template>
    </AppSimpleTable>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import AppSimpleTable, { type SimpleTableColumn } from '@/components/AppSimpleTable.vue'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { formatShortDateTime } from '@/utils/date'
import {
  createLateLink,
  fetchRegistrationManagement,
  revokeLateLink,
  type LateLink,
} from '@/utils/managementAPI'

const STATUS_LABELS: Record<LateLink['status'], string> = {
  active: 'Active',
  used: 'Used',
  expired: 'Expired',
  revoked: 'Revoked',
  signing_key_changed: 'Unavailable',
}

const columns: SimpleTableColumn[] = [
  { key: 'created', label: 'Created' },
  { key: 'expires', label: 'Expires' },
  { key: 'status', label: 'Status' },
  // Who registered with it, once it's used.
  { key: 'email', label: 'Email' },
]

const links = ref<LateLink[]>([])
const isLoading = ref(true)
const isCreating = ref(false)
const revokingId = ref<number | null>(null)
const copiedId = ref<number | null>(null)
const created = ref<LateLink | null>(null)
const error = ref('')

// How long a new link works for.
const LINK_DAYS = 3

const rows = computed(() =>
  links.value.map((link) => ({
    id: link.id,
    created: formatShortDateTime(link.created_at),
    expires: formatShortDateTime(link.expires_at),
    status: STATUS_LABELS[link.status],
    email: link.email || '—',
    link,
  })),
)
const toLink = (row: Record<string, unknown>) => row.link as LateLink

const load = async () => {
  try {
    links.value = (await fetchRegistrationManagement()).invitations
  } catch (err) {
    error.value = apiErrorFromUnknown(err, 'The late links could not be loaded.').message
  } finally {
    isLoading.value = false
  }
}

const create = async () => {
  isCreating.value = true
  error.value = ''
  try {
    created.value = await createLateLink(
      new Date(Date.now() + LINK_DAYS * 24 * 60 * 60 * 1000).toISOString(),
    )
    links.value = [created.value, ...links.value]
  } catch (err) {
    error.value = apiErrorFromUnknown(err, 'The late link could not be created.').message
  } finally {
    isCreating.value = false
  }
}

const revoke = async (link: LateLink) => {
  revokingId.value = link.id
  error.value = ''
  try {
    const revoked = await revokeLateLink(link.id)
    links.value = links.value.map((item) => (item.id === revoked.id ? revoked : item))
    if (created.value?.id === revoked.id) created.value = null
  } catch (err) {
    error.value = apiErrorFromUnknown(err, 'The late link could not be revoked.').message
  } finally {
    revokingId.value = null
  }
}

const copy = async (url: string, id: number) => {
  try {
    await navigator.clipboard.writeText(url)
    copiedId.value = id
    setTimeout(() => {
      if (copiedId.value === id) copiedId.value = null
    }, 2000)
  } catch {
    error.value = 'The link could not be copied. Select it and copy it instead.'
  }
}

onMounted(load)
</script>

<style scoped>
/* Laid out as Late Registration's other cards. */
.late-links {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.late-links__hint {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin: 0;
}

.late-links__form {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 1rem;
}

/* Each field as Extend Deadline's: its label small above it. */
/* The new link, on one line with Copy, wrapping when long. */
.late-links__created {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem;
  padding: 0.6rem 0.75rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
}

.late-links__url {
  flex: 1 1 20rem;
  min-width: 0;
  overflow-wrap: anywhere;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.82rem;
}

.late-links__actions {
  display: inline-flex;
  gap: 0.5rem;
}

.late-links__muted {
  color: var(--text-muted);
}

.late-links__status {
  font-weight: 600;
}

.late-links__status--active {
  color: var(--dark-green);
}

.late-links__status--used,
.late-links__status--expired,
.late-links__status--revoked,
.late-links__status--signing_key_changed {
  color: var(--text-muted);
}

.late-links__error {
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  margin: 0;
  background: color-mix(in srgb, var(--danger) 12%, transparent);
  color: var(--danger);
}
</style>
