<template>
  <div class="non-finalist">
    <section class="card">
      <div class="card-header">
        <h3 class="card-title">Email Nonfinalist</h3>
      </div>
      <!-- Laid out like Notify Finalists: the page title over a divider, then
           a section heading. -->
      <h3 class="non-finalist__section-title">Email Nonfinalist</h3>
      <p class="non-finalist__hint">
        For teams that submitted but weren't selected as finalists.
      </p>
      <p class="non-finalist__hint">
        The Symposium date and registration link come from Email Details on
        <RouterLink to="/management/notify-finalists">Notify Finalists</RouterLink>.
      </p>
      <p v-if="loadError" class="non-finalist__load-error">
        Failed to load the teams. {{ loadError }}
      </p>
      <template v-else-if="status">
        <!-- Same status line and count as Notify Finalists. A team only counts
             as emailed once every member got the email. -->
        <p
          v-if="status.teams.total"
          class="non-finalist__status"
          :class="allEmailed ? 'non-finalist__status--ok' : 'non-finalist__status--warn'"
        >
          <i :class="allEmailed ? 'fas fa-envelope-circle-check' : 'fas fa-envelope'" aria-hidden="true"></i>
          {{ allEmailed ? 'Emails are sent to every group member' : 'Emails are not sent to every group member' }}
        </p>
        <p v-if="status.teams.total" class="non-finalist__counts">
          Students: {{ status.students.emailed }} of {{ status.students.total }} emailed
        </p>
        <p v-if="status.blocked" class="non-finalist__blocked">{{ status.blocked }}</p>
        <div class="non-finalist__actions">
          <button
            type="button"
            class="btn btn-primary btn-sm"
            :disabled="sending || !canSend"
            @click="confirming = true"
          >
            {{ sending ? 'Sending…' : 'Email Nonfinalists' }}
          </button>
          <button
            type="button"
            class="btn btn-outline btn-sm"
            :disabled="loadingPreview"
            @click="openPreview"
          >
            {{ loadingPreview ? 'Loading…' : 'Preview Email' }}
          </button>
          <span v-if="sending" class="non-finalist__progress" role="status">
            Emailed {{ plural(progress.emailed, 'person', 'people') }} so far…
          </span>
        </div>
      </template>
    </section>

    <p v-if="actionError" class="non-finalist__banner non-finalist__banner--error">
      {{ actionError }}
    </p>
    <p v-if="actionMessage" class="non-finalist__banner non-finalist__banner--ok">
      {{ actionMessage }}
    </p>
  </div>

  <Teleport to="body">
    <div v-if="confirming" class="non-finalist__overlay" @click.self="confirming = false">
      <div class="non-finalist__dialog" role="dialog" aria-modal="true" aria-label="Send the non-finalist email">
        <h3 class="non-finalist__dialog-title">
          <i class="fas fa-envelope" aria-hidden="true"></i> Email non-finalist teams?
        </h3>
        <p class="non-finalist__dialog-text">
          This emails every member of the {{ plural(pendingTeams, 'team') }} that
          {{ pendingTeams === 1 ? "hasn't" : "haven't" }} had this email yet.
        </p>
        <div class="non-finalist__dialog-actions">
          <button type="button" class="btn btn-outline btn-sm" @click="confirming = false">Cancel</button>
          <button type="button" class="btn btn-primary btn-sm" @click="sendAll">Send</button>
        </div>
      </div>
    </div>
  </Teleport>

  <Teleport to="body">
    <div v-if="preview" class="non-finalist__overlay" @click.self="preview = null">
      <div
        class="non-finalist__dialog non-finalist__dialog--preview"
        role="dialog"
        aria-modal="true"
        aria-label="Email preview"
      >
        <h3 class="non-finalist__dialog-title">
          <i class="fas fa-envelope-open-text" aria-hidden="true"></i> {{ preview.subject }}
        </h3>
        <p class="non-finalist__dialog-text">
          As {{ preview.to }} would get it. Nothing has been sent.
        </p>
        <!-- As on Notify Finalists: the frame is as tall as the email and this
             box scrolls; sandbox without allow-scripts shows the email, never
             runs it; allow-same-origin only lets fitPreview measure it. -->
        <div class="non-finalist__preview-body">
          <iframe
            class="non-finalist__preview-frame"
            :srcdoc="preview.html"
            title="Email preview"
            sandbox="allow-same-origin"
            scrolling="no"
            @load="fitPreview"
          ></iframe>
        </div>
        <div class="non-finalist__dialog-actions">
          <button type="button" class="btn btn-outline btn-sm" @click="preview = null">Close</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useFlashMessage } from '@/composables/useFlashMessage'
import {
  fetchNonFinalistEmail,
  previewNonFinalistEmail,
  sendNonFinalistEmailBatch,
  type NonFinalistEmailPreview,
  type NonFinalistEmailStatus
} from '@/utils/gradingAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'

const plural = (n: number, word: string, words = `${word}s`) => `${n} ${n === 1 ? word : words}`

const status = ref<NonFinalistEmailStatus | null>(null)
const loadError = ref('')
const actionError = ref('')
const { message: actionMessage, show: flashAction } = useFlashMessage()

const load = async () => {
  loadError.value = ''
  try {
    status.value = await fetchNonFinalistEmail()
  } catch (err) {
    loadError.value = apiErrorFromUnknown(err).message
  }
}

const pendingTeams = computed(() => (status.value ? status.value.teams.total - status.value.teams.emailed : 0))
const allEmailed = computed(() => Boolean(status.value?.teams.total) && pendingTeams.value === 0)
const canSend = computed(() => Boolean(status.value && !status.value.blocked && pendingTeams.value > 0))

// -- Preview ----------------------------------------------------------------

const preview = ref<NonFinalistEmailPreview | null>(null)
const loadingPreview = ref(false)

const openPreview = async () => {
  actionError.value = ''
  loadingPreview.value = true
  try {
    preview.value = await previewNonFinalistEmail()
  } catch (err) {
    actionError.value = apiErrorFromUnknown(err).message
  } finally {
    loadingPreview.value = false
  }
}

// Grow the frame to the whole email, so only the dialog's box scrolls.
const fitPreview = (event: Event) => {
  const frame = event.target as HTMLIFrameElement
  const page = frame.contentDocument?.documentElement
  if (page) frame.style.height = `${page.scrollHeight}px`
}

// -- Sending ----------------------------------------------------------------

const confirming = ref(false)
const sending = ref(false)
const progress = ref({ emailed: 0, failed: 0 })

// A few teams at a time, so no single request runs long; progress shows between.
const sendAll = async () => {
  confirming.value = false
  actionError.value = ''
  sending.value = true
  progress.value = { emailed: 0, failed: 0 }
  let cursor: number | null = null
  try {
    for (;;) {
      const batch = await sendNonFinalistEmailBatch(cursor)
      progress.value = {
        emailed: progress.value.emailed + batch.emailed,
        failed: progress.value.failed + batch.failed
      }
      if (status.value) {
        status.value = { ...status.value, teams: batch.teams, students: batch.students }
      }
      cursor = batch.cursor
      if (batch.done) break
    }
    const { emailed, failed } = progress.value
    const sent = `Emailed ${plural(emailed, 'person', 'people')}.`
    if (failed) {
      actionError.value =
        `${sent} ${plural(failed, 'team')} ${failed === 1 ? "wasn't" : "weren't"} emailed in full; ` +
        'press Email Nonfinalists again to retry.'
    } else {
      flashAction(sent)
    }
  } catch (err) {
    actionError.value = apiErrorFromUnknown(err).message
  } finally {
    sending.value = false
    await load()
  }
}

onMounted(load)
</script>

<style scoped>
/* As on Notify Finalists. */
.non-finalist {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* As "Change Deadline". */
.non-finalist__section-title {
  font-size: 1.05rem;
  font-weight: 600;
  margin-bottom: 0.75rem;
}

.non-finalist__hint {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin-bottom: 0.75rem;
}

.non-finalist__hint a {
  color: var(--dark-green);
}

.non-finalist__load-error {
  margin: 0;
}

.non-finalist__status {
  font-weight: 600;
  font-size: 0.9rem;
  margin: 0 0 0.75rem;
}

.non-finalist__status--ok {
  color: var(--dark-green);
}

.non-finalist__status--warn {
  color: #eab308;
}

/* The size of the hint lines. */
.non-finalist__counts {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin: 0 0 0.75rem;
}

.non-finalist__blocked {
  color: #b8860b;
  font-size: 0.85rem;
  margin: 0 0 0.75rem;
}

.non-finalist__actions {
  display: flex;
  align-items: center;
  gap: 1.25rem;
}

.non-finalist__progress {
  color: var(--text-muted);
  font-size: 0.85rem;
}

.non-finalist__banner {
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  margin: 0;
}

.non-finalist__banner--error {
  background: color-mix(in srgb, var(--danger) 12%, transparent);
  color: var(--danger);
}

.non-finalist__banner--ok {
  background: var(--accent-green-soft);
  color: var(--dark-green);
}

/* Dialogs as on Notify Finalists and Release Results. */
.non-finalist__overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  z-index: 2000;
}

.non-finalist__dialog {
  background: var(--surface-elevated);
  color: var(--charcoal);
  border-radius: 10px;
  box-shadow: 0 10px 40px var(--shadow);
  width: 100%;
  max-width: 26rem;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.non-finalist__dialog.non-finalist__dialog--preview {
  max-width: 44rem;
  max-height: calc(100vh - 2rem);
}

.non-finalist__dialog-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.15rem;
  margin: 0;
}

.non-finalist__dialog-title i {
  color: var(--dark-green);
}

.non-finalist__dialog-text {
  color: var(--text-muted);
  font-size: 0.92rem;
  margin: 0;
}

.non-finalist__dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}

.non-finalist__preview-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: #eef0ee;
}

.non-finalist__preview-frame {
  display: block;
  width: 100%;
  height: 60vh;
  border: 0;
}
</style>
