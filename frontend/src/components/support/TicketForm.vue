<template>
  <form class="ticket-form" @submit.prevent="submit">
    <h2 class="ticket-form__title">Submit an enquiry</h2>
    <p class="ticket-form__lede">
      Tell us what is going on and we will get back to you. You will be able to follow the
      conversation from this page.
    </p>

    <label class="ticket-form__field">
      <span class="ticket-form__label">Category</span>
      <select v-model="category" required class="ticket-form__control">
        <option v-for="option in TICKET_CATEGORIES" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>
    </label>

    <label class="ticket-form__field">
      <span class="ticket-form__label">Subject</span>
      <input
        v-model="subject"
        type="text"
        required
        maxlength="255"
        placeholder="A short summary"
        class="ticket-form__control"
      />
    </label>

    <label class="ticket-form__field">
      <span class="ticket-form__label">Message</span>
      <textarea
        v-model="body"
        required
        rows="6"
        :maxlength="MAX_BODY_LENGTH"
        placeholder="What happened, and what were you trying to do?"
        class="ticket-form__control ticket-form__control--area"
      ></textarea>
      <span class="ticket-form__counter" :class="{ 'ticket-form__counter--full': body.length >= MAX_BODY_LENGTH }">
        {{ body.length }}/{{ MAX_BODY_LENGTH }}
      </span>
    </label>

    <TicketAttachmentPicker v-model="files" />

    <p v-if="error" class="ticket-form__error" role="alert">{{ error }}</p>

    <button type="submit" class="ticket-form__submit" :disabled="isSubmitting || !canSubmit">
      {{ isSubmitting ? 'Sending…' : 'Submit enquiry' }}
    </button>
  </form>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import TicketAttachmentPicker from '@/components/support/TicketAttachmentPicker.vue'
import { apiErrorFromUnknown } from '@/utils/apiError'
import {
  MAX_BODY_LENGTH,
  TICKET_CATEGORIES,
  submitTicket,
  type TicketCategory,
  type TicketDetail
} from '@/utils/supportAPI'

const emit = defineEmits<{ submitted: [TicketDetail] }>()

const category = ref<TicketCategory>(TICKET_CATEGORIES[0].value)
const subject = ref('')
const body = ref('')
const files = ref<File[]>([])
const isSubmitting = ref(false)
const error = ref('')

const canSubmit = computed(() => subject.value.trim().length > 0 && body.value.trim().length > 0)

async function submit() {
  if (isSubmitting.value || !canSubmit.value) return
  isSubmitting.value = true
  error.value = ''

  try {
    const ticket = await submitTicket({
      category: category.value,
      subject: subject.value.trim(),
      body: body.value.trim(),
      files: files.value
    })
    subject.value = ''
    body.value = ''
    files.value = []
    emit('submitted', ticket)
  } catch (err) {
    error.value = apiErrorFromUnknown(err, 'Could not submit your enquiry.').message
  } finally {
    isSubmitting.value = false
  }
}
</script>

<style scoped>
.ticket-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1.5rem;
  background: var(--surface-elevated);
  border: 1px solid var(--border-light);
  border-radius: 10px;
  box-shadow: 0 1px 3px var(--shadow);
}

.ticket-form__title {
  margin: 0;
  font-size: 1.3rem;
}

.ticket-form__lede {
  margin: -0.5rem 0 0 0;
  color: var(--text-muted);
  font-size: 0.9rem;
}

.ticket-form__field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  position: relative;
}

.ticket-form__label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--charcoal);
}

.ticket-form__control {
  padding: 0.6rem 0.75rem;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--white);
  color: var(--charcoal);
  font-family: inherit;
  font-size: 0.95rem;
}

.ticket-form__control:focus {
  outline: none;
  border-color: var(--dark-green);
  box-shadow: 0 0 0 3px var(--light-green);
}

.ticket-form__control--area {
  resize: vertical;
  min-height: 8rem;
}

.ticket-form__counter {
  align-self: flex-end;
  font-size: 0.78rem;
  color: var(--text-muted);
}

.ticket-form__counter--full {
  color: var(--danger);
  font-weight: 600;
}

.ticket-form__error {
  margin: 0;
  color: var(--danger);
  font-size: 0.88rem;
}

.ticket-form__submit {
  align-self: flex-start;
  padding: 0.65rem 1.4rem;
  border: none;
  border-radius: 6px;
  background: var(--dark-green);
  color: var(--white);
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
}

.ticket-form__submit:hover:not(:disabled) {
  background: var(--charcoal);
}

.ticket-form__submit:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
