<template>
  <!-- The same news in the app as an outcome email, for whoever the email
       has reached so far: preview it, edit its wording (the email's until
       edited) and post it. On Notify Finalist, Notify Nonfinalist and Release
       Results. -->
  <div v-if="announcement" class="outcome-announcement">
    <div class="outcome-announcement__actions">
      <button type="button" class="btn btn-outline btn-sm" @click="previewing = true">
        Preview {{ label }}
      </button>
      <button type="button" class="btn btn-outline btn-sm" @click="openEditor">
        Edit {{ label }}
      </button>
      <button
        type="button"
        class="btn btn-primary btn-sm"
        :disabled="posting || !announcement.recipients"
        @click="confirming = true"
      >
        {{ posting ? 'Posting…' : `Post ${label}` }}
      </button>
    </div>
    <p v-if="announcement.posted_at" class="outcome-announcement__posted" data-testid="announcement-posted">
      {{ label }} Last Posted at {{ shortDateTime(announcement.posted_at) }}<template
        v-if="announcement.posted_by"
      >
        by {{ announcement.posted_by }}</template
      >.
    </p>

    <!-- As the people it's for will see it in the app. -->
    <Teleport to="body">
      <div v-if="previewing" class="outcome-announcement__overlay" @click.self="previewing = false">
        <div
          class="outcome-announcement__dialog outcome-announcement__dialog--wide"
          role="dialog"
          aria-modal="true"
          :aria-label="`${label} preview`"
        >
          <h3 class="outcome-announcement__dialog-title">
            <i class="fas fa-bullhorn" aria-hidden="true"></i> {{ announcement.title }}
          </h3>
          <p class="outcome-announcement__dialog-text">
            As the {{ audience }} emailed so far will see it in the app. Nothing has been posted.
          </p>
          <!-- As the announcements page shows it, its boxes and buttons included. -->
          <!-- eslint-disable-next-line vue/no-v-html -- admin-written, shown as the announcements page does -->
          <div class="outcome-announcement__body" v-html="renderAnnouncementBody(announcement.body)"></div>
          <div class="outcome-announcement__dialog-actions">
            <button type="button" class="btn btn-outline btn-sm" @click="previewing = false">Close</button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="draft" class="outcome-announcement__overlay" @click.self="draft = null">
        <div
          class="outcome-announcement__dialog outcome-announcement__dialog--wide"
          role="dialog"
          aria-modal="true"
          :aria-label="`Edit ${label.toLowerCase()}`"
        >
          <h3 class="outcome-announcement__dialog-title">
            <i class="fas fa-pen" aria-hidden="true"></i> Edit {{ label }}
          </h3>
          <!-- Laid out as System Emails' editor: Title, Body, then its buttons. -->
          <div class="editor__field">
            <label class="editor__label" :for="`${kind}-announcement-title`">Title</label>
            <input
              :id="`${kind}-announcement-title`"
              v-model="draft.title"
              type="text"
              class="editor__title"
              maxlength="255"
              autocomplete="off"
              data-bwignore
              data-1p-ignore
              data-lpignore="true"
            />
          </div>
          <div class="editor__field outcome-announcement__editor">
            <span class="editor__label">Body</span>
            <!-- The announcements editor, with System Emails' Box and Button tools. -->
            <RichEditor v-model="draft.body" blocks compact placeholder="Write the announcement…" />
          </div>
          <p v-if="editError" class="outcome-announcement__error" role="alert">{{ editError }}</p>
          <footer class="editor__actions">
            <div class="editor__actions-primary">
              <button
                type="button"
                class="btn btn-primary"
                :disabled="saving || !draftChanged || !draft.title.trim()"
                @click="save"
              >
                <i :class="saving ? 'fas fa-spinner fa-spin' : 'fas fa-floppy-disk'" aria-hidden="true"></i>
                <span>{{ saving ? 'Saving…' : 'Save changes' }}</span>
              </button>
              <button
                type="button"
                class="btn btn-outline"
                :disabled="saving || !announcement.edited"
                @click="restore"
              >
                <i class="fas fa-rotate-left" aria-hidden="true"></i>
                <span>Restore default</span>
              </button>
            </div>
            <button type="button" class="btn btn-outline" @click="draft = null">Cancel</button>
          </footer>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="confirming" class="outcome-announcement__overlay" @click.self="confirming = false">
        <div
          class="outcome-announcement__dialog"
          role="dialog"
          aria-modal="true"
          :aria-label="`Post ${label.toLowerCase()}`"
        >
          <h3 class="outcome-announcement__dialog-title">
            <i class="fas fa-bullhorn" aria-hidden="true"></i> Post {{ label.toLowerCase() }}?
          </h3>
          <p class="outcome-announcement__dialog-text">
            This posts it in the app to the {{ audience }} emailed so
            far.<template v-if="announcement.posted_at"> It updates the one posted before.</template>
          </p>
          <div class="outcome-announcement__dialog-actions">
            <button type="button" class="btn btn-outline btn-sm" @click="confirming = false">Cancel</button>
            <button type="button" class="btn btn-primary btn-sm" @click="post">Post</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, ref } from 'vue'
import { renderAnnouncementBody } from '@/composables/useAnnouncements'
import {
  fetchOutcomeAnnouncement,
  postOutcomeAnnouncement,
  restoreOutcomeAnnouncement,
  updateOutcomeAnnouncement,
  type OutcomeAnnouncement,
  type OutcomeAnnouncementKind
} from '@/utils/managementAPI'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { plural } from '@/utils/string'

const props = withDefaults(
  defineProps<{
    kind: OutcomeAnnouncementKind
    /** What the buttons call it, e.g. "Group Announcement". */
    label?: string
  }>(),
  { label: 'Announcement' }
)

// What it did, for the page's banner under its card.
const emit = defineEmits<{
  flash: [text: string]
  error: [text: string]
}>()

// The rich editor loads only once Edit is opened.
const RichEditor = defineAsyncComponent(() => import('@/components/admin/RichEditor.vue'))

const announcement = ref<OutcomeAnnouncement | null>(null)
const previewing = ref(false)
const confirming = ref(false)
const posting = ref(false)
const saving = ref(false)
const editError = ref('')
// The wording being edited; null = the editor is closed.
const draft = ref<{ title: string; body: string } | null>(null)

// "2 finalist groups", "1 supervisor".
const audience = computed(() =>
  announcement.value ? plural(announcement.value.recipients, announcement.value.noun) : ''
)

const load = async () => {
  try {
    announcement.value = await fetchOutcomeAnnouncement(props.kind)
  } catch {
    // Best effort: without it the buttons just don't show.
  }
}

const openEditor = () => {
  if (!announcement.value) return
  editError.value = ''
  draft.value = { title: announcement.value.title, body: announcement.value.body }
}

// Something to save: the wording differs from what's saved.
const draftChanged = computed(
  () =>
    Boolean(draft.value && announcement.value) &&
    (draft.value!.title !== announcement.value!.title || draft.value!.body !== announcement.value!.body)
)

// Back to the email's wording, shown in the editor at once.
const restore = async () => {
  saving.value = true
  editError.value = ''
  try {
    announcement.value = await restoreOutcomeAnnouncement(props.kind)
    draft.value = { title: announcement.value.title, body: announcement.value.body }
    emit('flash', "Restored the email's wording.")
  } catch (err) {
    editError.value = apiErrorFromUnknown(err).message
  } finally {
    saving.value = false
  }
}

const save = async () => {
  if (!draft.value) return
  saving.value = true
  editError.value = ''
  try {
    announcement.value = await updateOutcomeAnnouncement(props.kind, draft.value)
    draft.value = null
    emit('flash', `${props.label} saved.`)
  } catch (err) {
    editError.value = apiErrorFromUnknown(err).message
  } finally {
    saving.value = false
  }
}

const post = async () => {
  confirming.value = false
  posting.value = true
  try {
    announcement.value = await postOutcomeAnnouncement(props.kind)
    emit('flash', `${props.label} posted to ${audience.value}.`)
  } catch (err) {
    emit('error', apiErrorFromUnknown(err).message)
  } finally {
    posting.value = false
  }
}

// "02/10/2026 18:36", as Last Emailed writes it.
const shortDateTime = (iso: string) => {
  const at = new Date(iso)
  return `${at.toLocaleDateString('en-GB')} ${at.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })}`
}

onMounted(load)

// The page reloads it once a send finishes: more reached, more who'd see it.
defineExpose({ reload: load })
</script>

<!-- Edit's title box, fields and button bar, as System Emails' editor. -->
<style scoped src="../../components/admin/editorForm.css"></style>

<style scoped>
.outcome-announcement {
  margin-top: 0.75rem;
}

.outcome-announcement__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem 1.25rem;
}

/* As Last Emailed. */
.outcome-announcement__posted {
  color: var(--text-muted);
  font-size: 0.85rem;
  margin: 1rem 0 0;
}

.outcome-announcement__error {
  color: var(--danger);
  font-size: 0.85rem;
  margin: 0;
}

.outcome-announcement__overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  z-index: 2000;
}

.outcome-announcement__dialog {
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

/* Preview and Edit: wider, and always fitting the window. */
.outcome-announcement__dialog.outcome-announcement__dialog--wide {
  max-width: 44rem;
  max-height: calc(100vh - 2rem);
}

.outcome-announcement__dialog-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.15rem;
  margin: 0;
}

.outcome-announcement__dialog-title i {
  color: var(--dark-green);
}

.outcome-announcement__dialog-text {
  color: var(--text-muted);
  font-size: 0.92rem;
  margin: 0;
}

.outcome-announcement__dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}

/* The announcement as the app shows it, scrolling if it's long. */
.outcome-announcement__body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0.75rem 1rem;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  font-size: 0.95rem;
  line-height: 1.55;
}

.outcome-announcement__body :deep(p),
.outcome-announcement__body :deep(ul) {
  margin: 0 0 0.75rem;
}

.outcome-announcement__editor {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}
</style>
