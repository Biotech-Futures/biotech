<template>
  <!-- One Symposium email on the Email Nonfinalist tab: the page's headings
       and text in the slot, then who has it, why it can't go if it can't,
       sending and a preview. -->
  <div class="symposium-email" :class="`symposium-email--${email}`">
    <section class="card">
      <slot />
      <p v-if="loadError" class="symposium-email__load-error">
        Failed to load the teams. {{ loadError }}
      </p>
      <template v-else-if="status">
        <!-- Same status line and count as Notify Finalists, shown even while
             no team is due it. A team only counts as emailed once every
             member got the email. -->
        <p
          class="symposium-email__status"
          :class="allEmailed ? 'symposium-email__status--ok' : 'symposium-email__status--warn'"
        >
          <i :class="allEmailed ? 'fas fa-envelope-circle-check' : 'fas fa-envelope'" aria-hidden="true"></i>
          {{ allEmailed ? 'Emails are sent to every group member' : 'Emails are not sent to every group member' }}
        </p>
        <p class="symposium-email__counts">
          Students: {{ status.students.emailed }} of {{ status.students.total }} emailed
        </p>
        <p v-if="status.blocked" class="symposium-email__blocked">{{ status.blocked }}</p>
        <div class="symposium-email__actions">
          <button
            type="button"
            class="btn btn-primary btn-sm"
            :disabled="sending || !canSend"
            @click="confirming = true"
          >
            {{ sending ? 'Sending…' : buttonLabel }}
          </button>
          <button
            type="button"
            class="btn btn-outline btn-sm"
            :disabled="loadingPreview"
            @click="openPreview"
          >
            {{ loadingPreview ? 'Loading…' : 'Preview Email' }}
          </button>
          <TestEmailSender v-model:recipient="testRecipient" :kind="email" />
          <span v-if="sending" class="symposium-email__progress" role="status">
            Emailed {{ plural(progress.emailed, 'person', 'people') }} so far…
          </span>
        </div>
      </template>
    </section>

    <p v-if="actionError" class="symposium-email__banner symposium-email__banner--error">
      {{ actionError }}
    </p>
    <p v-if="actionMessage" class="symposium-email__banner symposium-email__banner--ok">
      {{ actionMessage }}
    </p>
  </div>

  <Teleport to="body">
    <div v-if="confirming" class="symposium-email__overlay" @click.self="confirming = false">
      <div class="symposium-email__dialog" role="dialog" aria-modal="true" aria-label="Send the email">
        <h3 class="symposium-email__dialog-title">
          <i class="fas fa-envelope" aria-hidden="true"></i> {{ confirmTitle }}
        </h3>
        <p class="symposium-email__dialog-text">
          This emails every member of the {{ plural(pendingTeams, 'team') }} that
          {{ pendingTeams === 1 ? "hasn't" : "haven't" }} had this email yet.
        </p>
        <div class="symposium-email__dialog-actions">
          <button type="button" class="btn btn-outline btn-sm" @click="confirming = false">Cancel</button>
          <button type="button" class="btn btn-primary btn-sm" @click="sendAll">Send</button>
        </div>
      </div>
    </div>
  </Teleport>

  <Teleport to="body">
    <div v-if="preview" class="symposium-email__overlay" @click.self="preview = null">
      <div
        class="symposium-email__dialog symposium-email__dialog--preview"
        role="dialog"
        aria-modal="true"
        aria-label="Email preview"
      >
        <h3 class="symposium-email__dialog-title">
          <i class="fas fa-envelope-open-text" aria-hidden="true"></i> {{ preview.subject }}
        </h3>
        <p class="symposium-email__dialog-text">
          As {{ preview.to }} would get it. Nothing has been sent.
        </p>
        <!-- As on Notify Finalists: the frame is as tall as the email and this
             box scrolls; sandbox without allow-scripts shows the email, never
             runs it; allow-same-origin only lets fitPreview measure it. -->
        <div class="symposium-email__preview-body">
          <iframe
            class="symposium-email__preview-frame"
            :srcdoc="preview.html"
            title="Email preview"
            sandbox="allow-same-origin"
            scrolling="no"
            @load="fitPreview"
          ></iframe>
        </div>
        <div class="symposium-email__dialog-actions">
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
  fetchSymposiumEmail,
  previewSymposiumEmail,
  sendSymposiumEmailBatch,
  type SymposiumEmail,
  type SymposiumEmailPreview,
  type SymposiumEmailStatus
} from '@/utils/gradingAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'
import TestEmailSender from '@/views/grading/TestEmailSender.vue'

const props = defineProps<{
  email: SymposiumEmail
  /** The send button, e.g. "Email Nonfinalists". */
  buttonLabel: string
  /** The confirmation's question, e.g. "Email non-finalist teams?". */
  confirmTitle: string
}>()

const plural = (n: number, word: string, words = `${word}s`) => `${n} ${n === 1 ? word : words}`

const status = ref<SymposiumEmailStatus | null>(null)
const loadError = ref('')
const actionError = ref('')
const { message: actionMessage, show: flashAction } = useFlashMessage()

const load = async () => {
  loadError.value = ''
  try {
    status.value = await fetchSymposiumEmail(props.email)
  } catch (err) {
    loadError.value = apiErrorFromUnknown(err).message
  }
}

const pendingTeams = computed(() => (status.value ? status.value.teams.total - status.value.teams.emailed : 0))
const allEmailed = computed(() => Boolean(status.value?.teams.total) && pendingTeams.value === 0)
const canSend = computed(() => Boolean(status.value && !status.value.blocked && pendingTeams.value > 0))

// -- Preview ----------------------------------------------------------------

const preview = ref<SymposiumEmailPreview | null>(null)
const loadingPreview = ref(false)
// The person picked in Send Test Email: the preview is their team's email.
const testRecipient = ref('')

const openPreview = async () => {
  actionError.value = ''
  loadingPreview.value = true
  try {
    preview.value = await previewSymposiumEmail(props.email, testRecipient.value)
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
      const batch = await sendSymposiumEmailBatch(props.email, cursor)
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
        `press ${props.buttonLabel} again to retry.`
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
.symposium-email {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.symposium-email__load-error {
  margin: 0;
}

/* As on Notify Finalists. */
.symposium-email__status {
  font-weight: 600;
  font-size: 0.9rem;
  margin: 0 0 0.75rem;
}

.symposium-email__status--ok {
  color: var(--dark-green);
}

.symposium-email__status--warn {
  color: #eab308;
}

/* The size of the hint lines. */
.symposium-email__counts {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin: 0 0 0.75rem;
}

.symposium-email__blocked {
  color: #b8860b;
  font-size: 0.85rem;
  margin: 0 0 0.75rem;
}

.symposium-email__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem 1.25rem;
}

.symposium-email__progress {
  color: var(--text-muted);
  font-size: 0.85rem;
}

.symposium-email__banner {
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.9rem;
  margin: 0;
}

.symposium-email__banner--error {
  background: color-mix(in srgb, var(--danger) 12%, transparent);
  color: var(--danger);
}

.symposium-email__banner--ok {
  background: var(--accent-green-soft);
  color: var(--dark-green);
}

/* Dialogs as on Notify Finalists and Release Results. */
.symposium-email__overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  z-index: 2000;
}

.symposium-email__dialog {
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

.symposium-email__dialog.symposium-email__dialog--preview {
  max-width: 44rem;
  max-height: calc(100vh - 2rem);
}

.symposium-email__dialog-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.15rem;
  margin: 0;
}

.symposium-email__dialog-title i {
  color: var(--dark-green);
}

.symposium-email__dialog-text {
  color: var(--text-muted);
  font-size: 0.92rem;
  margin: 0;
}

.symposium-email__dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}

.symposium-email__preview-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: #eef0ee;
}

.symposium-email__preview-frame {
  display: block;
  width: 100%;
  height: 60vh;
  border: 0;
}
</style>
