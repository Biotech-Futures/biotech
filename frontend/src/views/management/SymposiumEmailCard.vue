<template>
  <!-- One Symposium email on the Notify Nonfinalist tab: the page's headings
       and text in the slot, then a preview, who has it, why it can't go if
       it can't, and sending. -->
  <div class="symposium-email" :class="`symposium-email--${email}`">
    <section class="card">
      <slot />
      <p v-if="loadError" class="symposium-email__load-error">
        Failed to load the teams. {{ loadError }}
      </p>
      <template v-else-if="status">
        <!-- Preview and test above who has it. -->
        <div class="symposium-email__actions symposium-email__actions--preview">
          <button
            type="button"
            class="btn btn-outline btn-sm"
            :disabled="loadingPreview"
            @click="openPreview()"
          >
            {{ loadingPreview ? 'Loading…' : 'Preview Email' }}
          </button>
          <TestEmailSender v-model:recipient="testRecipient" :kind="email" />
        </div>
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
          <strong>Groups: {{ status.groups.emailed }} of {{ status.groups.total }} emailed</strong><br />
          Students: {{ status.students.emailed }} of {{ status.students.total }} emailed ·
          Mentors: {{ status.mentors.emailed }} of {{ status.mentors.total }} emailed
          (Times {{ status.mentors.times.emailed }} of {{ status.mentors.times.total }}) ·
          Supervisors: {{ status.supervisors.emailed }} of {{ status.supervisors.total }} emailed
          (Times {{ status.supervisors.times.emailed }} of {{ status.supervisors.times.total }})
        </p>
        <p v-if="status.blocked" class="symposium-email__blocked">{{ status.blocked }}</p>
        <div class="symposium-email__actions">
          <button
            type="button"
            class="btn btn-primary btn-sm"
            :disabled="starting !== null || !canSend"
            @click="confirming = 'all'"
          >
            {{ starting === 'all' ? 'Sending…' : buttonLabel }}
          </button>
          <button
            v-if="newlyAdded"
            type="button"
            class="btn btn-outline btn-sm"
            :disabled="starting !== null || !canSend || !status.waiting.new.teams"
            @click="confirming = 'new'"
          >
            {{ starting === 'new' ? 'Sending…' : 'Email Newly Added' }}
          </button>
          <button
            type="button"
            class="btn btn-outline btn-sm"
            :disabled="starting !== null || !canSend || !status.waiting.missed.teams"
            @click="confirming = 'missed'"
          >
            {{ starting === 'missed' ? 'Sending…' : 'Resend Email To Missed Individuals' }}
          </button>
          <span v-if="status.sending && status.run" class="symposium-email__progress" role="status">
            Emailed {{ status.run.emailed }} of {{ plural(status.run.due, 'person', 'people') }} so far…
          </span>
          <span v-if="status.queued" class="symposium-email__queued" role="status">
            {{ queuedNote(status.queued, status.ahead) }}
          </span>
        </div>
        <div v-if="status.run?.missed.length" class="symposium-email__missed" data-testid="missed">
          <p class="symposium-email__missed-title">Couldn't be emailed:</p>
          <ul>
            <li v-for="(m, i) in status.run.missed" :key="i">
              <MissedPerson :who="m.who" /><span v-if="m.reason" class="symposium-email__missed-reason"> · {{ m.reason }}</span>
            </li>
          </ul>
        </div>
        <!-- The same news in the app, for the groups emailed so far. -->
        <OutcomeAnnouncement
          ref="announcement"
          :kind="email"
          @flash="flashAction"
          @error="(text) => (actionError = text)"
        />
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
    <div v-if="confirming" class="symposium-email__overlay" @click.self="confirming = null">
      <div class="symposium-email__dialog" role="dialog" aria-modal="true" aria-label="Send the email">
        <h3 class="symposium-email__dialog-title">
          <i class="fas fa-envelope" aria-hidden="true"></i> {{ confirmTitle }}
        </h3>
        <p v-if="confirming === 'new' && status" class="symposium-email__dialog-text">
          This emails every member of the {{ plural(status.waiting.new.teams, 'newly added team') }}.
        </p>
        <p v-else-if="confirming === 'missed' && status" class="symposium-email__dialog-text">
          This emails only the {{ plural(status.waiting.missed.people, 'person', 'people') }} earlier sends
          missed, on {{ plural(status.waiting.missed.teams, 'team') }}.
        </p>
        <p v-else class="symposium-email__dialog-text">
          This emails every member of the {{ plural(pendingTeams, 'team') }} that
          {{ pendingTeams === 1 ? "hasn't" : "haven't" }} had this email yet.
        </p>
        <div class="symposium-email__dialog-actions">
          <button type="button" class="btn btn-outline btn-sm" @click="confirming = null">Cancel</button>
          <button type="button" class="btn btn-primary btn-sm" @click="send">Send</button>
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
import { useEmailPreview } from '@/composables/useEmailPreview'
import { describeRun, isBusy, queuedMessage, queuedNote, RUN_MESSAGE_MS, useEmailRun } from '@/composables/useEmailRun'
import { useFlashMessage } from '@/composables/useFlashMessage'
import {
  fetchSymposiumEmail,
  previewSymposiumEmail,
  startSymposiumEmail,
  type EmailRun,
  type SymposiumEmail,
  type SymposiumEmailStatus
} from '@/utils/managementAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { plural } from '@/utils/string'
import MissedPerson from '@/views/management/MissedPerson.vue'
import OutcomeAnnouncement from '@/views/management/OutcomeAnnouncement.vue'
import TestEmailSender from '@/views/management/TestEmailSender.vue'

const props = defineProps<{
  email: SymposiumEmail
  /** The send button, e.g. "Email All Nonfinalists". */
  buttonLabel: string
  /** The confirmation's question, e.g. "Email non-finalist teams?". */
  confirmTitle: string
  /** Show Email Newly Added: only the teams no send has tried yet. */
  newlyAdded?: boolean
}>()

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
const canSend = computed(() =>
  Boolean(status.value && !status.value.blocked && pendingTeams.value > 0)
)

// -- Preview ----------------------------------------------------------------

// The group picked in Send Test Email: the preview is its email.
const testRecipient = ref('')
const { preview, loadingPreview, openPreview, fitPreview } = useEmailPreview(
  () => previewSymposiumEmail(props.email, testRecipient.value),
  actionError
)

// -- Sending ----------------------------------------------------------------

// Which send is awaiting confirmation: every team due, only those no send
// has tried yet, or only the people earlier sends missed; null = dialog closed.
type SendMode = 'all' | 'new' | 'missed'
const confirming = ref<SendMode | null>(null)
// Which Send request is going; the run then sends on the server.
const starting = ref<SendMode | null>(null)

const send = async () => {
  const mode = confirming.value
  if (!mode) return
  confirming.value = null
  actionError.value = ''
  starting.value = mode
  try {
    status.value = await (mode === 'all'
      ? startSymposiumEmail(props.email)
      : startSymposiumEmail(props.email, mode))
    // A run with little or nothing to send can be over by the reply.
    if (status.value.queued) flashAction(queuedMessage(status.value.ahead))
    else if (!isBusy(status.value) && status.value.run) reportRun(status.value.run)
  } catch (err) {
    actionError.value = apiErrorFromUnknown(err).message
  } finally {
    starting.value = null
  }
}

// The same news in the app, reloaded once a send finishes.
const announcement = ref<InstanceType<typeof OutcomeAnnouncement> | null>(null)

// How the run went, once this page saw it finish.
const reportRun = (run: EmailRun) => {
  const { text, isError } = describeRun(run, {
    emailed: ['person', 'people'],
    failed: 'team',
    button: 'Resend Email To Missed Individuals',
    sentFrom: status.value?.sent_from
  })
  if (isError) actionError.value = text
  else flashAction(text, RUN_MESSAGE_MS)
  // More groups emailed: more who'd see the announcement.
  void announcement.value?.reload()
}
useEmailRun(() => status.value, load, reportRun)

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

.symposium-email__actions--preview {
  margin: 0 0 0.75rem;
}

.symposium-email__progress {
  color: var(--text-muted);
  font-size: 0.85rem;
}

/* Who the last run couldn't reach, under the buttons. */
.symposium-email__missed {
  margin-top: 0.75rem;
  font-size: 0.85rem;
}

/* What a queued send waits behind: the colour of Couldn't be emailed. */
.symposium-email__queued {
  color: var(--danger);
  font-size: 0.85rem;
}

.symposium-email__missed-title {
  margin: 0 0 0.25rem;
  font-weight: 600;
  color: var(--danger);
}

.symposium-email__missed ul {
  margin: 0;
  padding-left: 1.2rem;
}

.symposium-email__missed-reason {
  color: var(--text-muted);
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
