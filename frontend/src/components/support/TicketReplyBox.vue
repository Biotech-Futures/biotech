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
      <TicketAttachmentPicker v-model="files" />
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
.reply {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 1rem;
  border: 1px solid var(--border-light);
  border-radius: 10px;
  background: var(--surface-elevated);
}

.reply__field {
  display: block;
}

.reply__control {
  width: 100%;
  padding: 0.6rem 0.75rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--white);
  color: var(--charcoal);
  font-family: inherit;
  font-size: 0.94rem;
  resize: vertical;
}

.reply__control:focus {
  outline: none;
  border-color: var(--dark-green);
  box-shadow: 0 0 0 3px var(--light-green);
}

.reply__footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
}

.reply__counter {
  margin-left: auto;
  font-size: 0.78rem;
  color: var(--text-muted);
}

.reply__send {
  padding: 0.55rem 1.2rem;
  border: none;
  border-radius: 6px;
  background: var(--dark-green);
  color: var(--white);
  font-weight: 600;
  font-size: 0.92rem;
  cursor: pointer;
}

.reply__send:hover:not(:disabled) {
  background: var(--charcoal);
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
