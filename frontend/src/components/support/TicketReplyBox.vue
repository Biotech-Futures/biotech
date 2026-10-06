<template>
  <form class="reply" @submit.prevent="send">
    <label class="reply__field">
      <span class="sr-only">Your reply</span>
      <textarea
        v-model="body"
        rows="4"
        :maxlength="MAX_BODY_LENGTH"
        :placeholder="placeholder"
        class="reply__control"
      ></textarea>
    </label>

    <div class="reply__footer">
      <TicketAttachmentPicker v-model="files" class="reply__attach" />
      <span class="reply__counter">{{ body.length }}/{{ MAX_BODY_LENGTH }}</span>
      <button type="submit" class="reply__send" :disabled="isSending || !body.trim()">
        {{ isSending ? 'Sending…' : 'Send reply' }}
      </button>
    </div>

    <p v-if="error" class="reply__error" role="alert">{{ error }}</p>
  </form>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import TicketAttachmentPicker from '@/components/support/TicketAttachmentPicker.vue'
import { apiErrorFromUnknown } from '@/utils/apiError'
import { MAX_BODY_LENGTH, replyToTicket, type TicketDetail } from '@/utils/supportAPI'

const props = defineProps<{ ticketId: number | string; isResolved?: boolean }>()
const emit = defineEmits<{ replied: [TicketDetail] }>()

const body = ref('')
const files = ref<File[]>([])
const isSending = ref(false)
const error = ref('')

// Says out loud what replying to a resolved ticket does, so nobody has to
// discover it by trying.
const placeholder = computed(() =>
  props.isResolved
    ? 'Still need help? Replying here will reopen this enquiry.'
    : 'Add anything that might help us.'
)

async function send() {
  if (isSending.value || !body.value.trim()) return
  isSending.value = true
  error.value = ''

  try {
    const ticket = await replyToTicket(props.ticketId, body.value.trim(), files.value)
    body.value = ''
    files.value = []
    emit('replied', ticket)
  } catch (err) {
    error.value = apiErrorFromUnknown(err, 'Could not send your reply.').message
  } finally {
    isSending.value = false
  }
}
</script>

<style scoped>
/* The first redesign round (October 2026): a soft card, a field with an edge
   you can see, one compact row of controls under it. Colours are the
   component's own so main.css stays every other team's.

   Measured on the card (white in light, #1d2826 in dark; WCAG AA, 4.5:1 for
   text and 3:1 for a field's edge):
     light  counter #5a6268 6.21:1   placeholder #6c757d 4.69:1
            field edge #84938f 3.21:1
     dark   counter #a3b3ae 6.95:1   placeholder #93a39e on the #161f1d field 6.39:1
            field edge #70827d on the field 4.15:1 */
.reply {
  --reply-muted: #5a6268;
  --reply-placeholder: #6c757d;
  --reply-edge: #84938f;
  --reply-focus-edge: var(--dark-green);
  --reply-card-edge: #e3e7e5;
  --reply-card-shadow: 0 1px 2px rgba(23, 66, 67, 0.06), 0 4px 12px rgba(23, 66, 67, 0.05);

  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 1rem 1rem 0.75rem;
  border: 1px solid var(--reply-card-edge);
  border-radius: 12px;
  background: var(--surface-elevated);
  box-shadow: var(--reply-card-shadow);
}

:root[data-theme="dark"] .reply {
  --reply-muted: #a3b3ae;
  --reply-placeholder: #93a39e;
  --reply-edge: #70827d;
  --reply-focus-edge: #6dbfb1;
  --reply-card-edge: #2b3936;
  --reply-card-shadow: 0 1px 3px var(--shadow);
}

.reply__field {
  display: block;
}

/* Block, so the field leaves no descender gap under it in the label. */
.reply__control {
  display: block;
  width: 100%;
  padding: 0.65rem 0.875rem;
  border: 1px solid var(--reply-edge);
  border-radius: 8px;
  background: var(--white);
  color: var(--charcoal);
  font-family: inherit;
  font-size: 0.95rem;
  resize: vertical;
}

.reply__control::placeholder {
  color: var(--reply-placeholder);
  opacity: 1;
}

.reply__control:focus {
  outline: none;
  border-color: var(--reply-focus-edge);
  box-shadow: 0 0 0 3px var(--light-green);
}

.reply__footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
}

/* The picker's button is a step smaller here than in the new-ticket form,
   and sits a little further from its hint. */
.reply__footer > .reply__attach {
  gap: 0.75rem;
}

.reply__attach :deep(.attach__button) {
  min-height: 2rem;
  font-size: 0.85rem;
}

.reply__counter {
  margin-left: auto;
  font-size: 0.78rem;
  color: var(--reply-muted);
}

/* White in both themes, and a hover ground that stays dark: var(--white) and
   var(--charcoal) swap places in dark, which would put dark text on the
   green, then white text on a pale hover. */
.reply__send {
  min-height: 2.5rem;
  padding: 0.55rem 1.2rem;
  border: none;
  border-radius: 8px;
  background: var(--dark-green);
  color: #ffffff;
  font-weight: 600;
  font-size: 0.92rem;
  cursor: pointer;
}

.reply__send:hover:not(:disabled) {
  background: #174243;
}

.reply__send:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.reply__error {
  margin: 0;
  color: var(--danger);
  font-size: 0.86rem;
}
</style>
